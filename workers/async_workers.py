"""
PaperMiner - Async Workers
QThread-based workers for all long-running operations:
  - AI chat (LLM API calls)
  - Paper indexing (text extraction + embedding)
  - Paper discovery (ArXiv/HF search)
  - PDF download
"""

import logging
from typing import Optional, List

from PyQt6.QtCore import QThread, pyqtSignal, QObject

from core.database import DatabaseManager
from core.models import TextChunk

logger = logging.getLogger(__name__)


class ChatWorker(QThread):
    """
    Worker thread for AI chat interactions.
    Prevents UI freezing during LLM API calls.
    """
    response_ready = pyqtSignal(str)       # Full response text
    chunk_received = pyqtSignal(str)       # Streaming chunk
    error_occurred = pyqtSignal(str)       # Error message
    finished_signal = pyqtSignal()         # Work complete

    def __init__(self, db: DatabaseManager, mode: str, message: str,
                 paper_id: Optional[int] = None, parent: QObject = None) -> None:
        super().__init__(parent)
        self.db = db
        self.mode = mode           # "Chat with Paper" | "Chat with Library" | "Free Chat"
        self.message = message
        self.paper_id = paper_id

    def run(self) -> None:
        try:
            from ai.chat_handler import ChatHandler

            handler = ChatHandler(self.db)

            if self.mode == "Chat with Paper" and self.paper_id is not None:
                response = handler.chat_with_paper(self.paper_id, self.message)
            elif self.mode == "Chat with Library":
                response = handler.chat_with_library(self.message)
            else:
                response = handler.free_chat(self.message)

            self.response_ready.emit(response)
        except Exception as e:
            logger.error(f"ChatWorker error: {e}")
            self.error_occurred.emit(str(e))
        finally:
            self.finished_signal.emit()


class IndexWorker(QThread):
    """
    Worker thread for paper indexing (RAG pipeline).
    Extracts text, chunks it, generates embeddings, and saves to DB.
    """
    progress = pyqtSignal(str)             # Status message
    finished_signal = pyqtSignal(int)      # paper_id when done
    error_occurred = pyqtSignal(str)

    def __init__(self, db: DatabaseManager, paper_id: int,
                 file_path: str, parent: QObject = None) -> None:
        super().__init__(parent)
        self.db = db
        self.paper_id = paper_id
        self.file_path = file_path

    def run(self) -> None:
        try:
            from ai.rag_engine import index_paper

            self.progress.emit("Extracting text from PDF...")
            chunks = index_paper(self.file_path)

            if not chunks:
                self.error_occurred.emit("No text could be extracted from this PDF.")
                return

            self.progress.emit(f"Saving {len(chunks)} chunks to database...")
            for chunk in chunks:
                chunk.paper_id = self.paper_id
            self.db.save_chunks(self.paper_id, chunks)
            self.db.set_paper_indexed(self.paper_id, True)

            self.progress.emit(f"Indexing complete: {len(chunks)} chunks.")
            self.finished_signal.emit(self.paper_id)
        except Exception as e:
            logger.error(f"IndexWorker error: {e}")
            self.error_occurred.emit(str(e))


class SearchWorker(QThread):
    """
    Worker thread for paper discovery searches (ArXiv, HuggingFace).
    """
    results_ready = pyqtSignal(list)       # List of result dicts
    error_occurred = pyqtSignal(str)
    finished_signal = pyqtSignal()

    def __init__(self, source: str, keyword: str, max_results: int = 10,
                 sort_by: str = "relevance", parent: QObject = None) -> None:
        super().__init__(parent)
        self.source = source
        self.keyword = keyword
        self.max_results = max_results
        self.sort_by = sort_by

    def run(self) -> None:
        try:
            results = []

            if self.source in ("ArXiv", "Both"):
                from discovery.arxiv_client import search_arxiv
                arxiv_results = search_arxiv(
                    self.keyword, max_results=self.max_results, sort_by=self.sort_by
                )
                results.extend(arxiv_results)

            if self.source in ("HuggingFace Daily Papers", "Both"):
                from discovery.hf_client import search_hf_papers
                hf_results = search_hf_papers(self.keyword, max_results=self.max_results)
                results.extend(hf_results)

            self.results_ready.emit(results)
        except Exception as e:
            logger.error(f"SearchWorker error: {e}")
            self.error_occurred.emit(str(e))
        finally:
            self.finished_signal.emit()


class DownloadWorker(QThread):
    """
    Worker thread for downloading papers (e.g., from ArXiv).
    """
    progress = pyqtSignal(str)
    download_complete = pyqtSignal(str)    # Local file path
    error_occurred = pyqtSignal(str)

    def __init__(self, url: str, save_dir: str, filename: str,
                 parent: QObject = None) -> None:
        super().__init__(parent)
        self.url = url
        self.save_dir = save_dir
        self.filename = filename

    def run(self) -> None:
        try:
            import httpx
            from pathlib import Path

            dest = Path(self.save_dir) / self.filename
            self.progress.emit(f"Downloading {self.filename}...")

            with httpx.Client(timeout=60.0, follow_redirects=True) as client:
                with client.stream("GET", self.url) as response:
                    response.raise_for_status()
                    with open(dest, "wb") as f:
                        for chunk in response.iter_bytes(chunk_size=8192):
                            f.write(chunk)

            self.progress.emit(f"Download complete: {self.filename}")
            self.download_complete.emit(str(dest))
        except Exception as e:
            logger.error(f"DownloadWorker error: {e}")
            self.error_occurred.emit(str(e))
