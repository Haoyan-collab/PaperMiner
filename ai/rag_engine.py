"""
PaperMiner - RAG Engine
Responsible for:
  1. PDF text extraction (via pymupdf/fitz)
  2. Text chunking with overlap
  3. Embedding generation (local sentence-transformers or API)
  4. Simple vector similarity search (cosine similarity for MVP)
"""

import json
import logging
import math
import os
from pathlib import Path
from typing import List, Tuple, Optional

from config import settings, HF_MIRROR_URL
from core.models import TextChunk

logger = logging.getLogger(__name__)


# ---- Text Extraction ----

def extract_text_from_pdf(file_path: str) -> List[Tuple[int, str]]:
    """
    Extract text from a PDF file page-by-page.
    Returns list of (page_number, text) tuples.
    """
    try:
        import fitz  # pymupdf
    except ImportError:
        logger.error("pymupdf not installed. Run: pip install pymupdf")
        return []

    pages: List[Tuple[int, str]] = []
    try:
        doc = fitz.open(file_path)
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text("text")
            if text.strip():
                pages.append((page_num + 1, text.strip()))
        doc.close()
        logger.info(f"Extracted text from {len(pages)} pages of {os.path.basename(file_path)}")
    except Exception as e:
        logger.error(f"Failed to extract text from {file_path}: {e}")

    return pages


# ---- Text Chunking ----

def chunk_text(
    pages: List[Tuple[int, str]],
    chunk_size: int = 512,
    chunk_overlap: int = 64,
) -> List[TextChunk]:
    """
    Split page text into overlapping chunks for embedding.
    Each chunk tracks which page(s) it came from.
    """
    chunk_size = chunk_size or settings.chunk_size
    chunk_overlap = chunk_overlap or settings.chunk_overlap

    chunks: List[TextChunk] = []
    chunk_index = 0

    for page_num, text in pages:
        words = text.split()
        start = 0

        while start < len(words):
            end = start + chunk_size
            chunk_words = words[start:end]
            chunk_text_str = " ".join(chunk_words)

            if len(chunk_text_str.strip()) > 20:  # Skip very short chunks
                chunks.append(TextChunk(
                    chunk_index=chunk_index,
                    text=chunk_text_str,
                    page_start=page_num,
                    page_end=page_num,
                ))
                chunk_index += 1

            start += chunk_size - chunk_overlap

    logger.info(f"Created {len(chunks)} text chunks.")
    return chunks


# ---- Embedding Generation ----

class EmbeddingEngine:
    """Generates embeddings using local sentence-transformers or an API fallback."""

    def __init__(self) -> None:
        self._model = None
        self._use_local = settings.embedding.use_local

    def _load_local_model(self) -> None:
        """Lazy-load the local sentence-transformers model."""
        if self._model is not None:
            return

        try:
            # Set HuggingFace mirror for China mainland
            os.environ["HF_ENDPOINT"] = HF_MIRROR_URL

            from sentence_transformers import SentenceTransformer
            model_name = settings.embedding.local_model_name
            logger.info(f"Loading embedding model: {model_name} (mirror: {HF_MIRROR_URL})")
            self._model = SentenceTransformer(model_name)
            logger.info("Embedding model loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load local embedding model: {e}")
            self._use_local = False

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a list of texts."""
        if self._use_local:
            return self._embed_local(texts)
        else:
            return self._embed_api(texts)

    def _embed_local(self, texts: List[str]) -> List[List[float]]:
        """Use local sentence-transformers model."""
        self._load_local_model()
        if self._model is None:
            return [[] for _ in texts]

        try:
            embeddings = self._model.encode(texts, show_progress_bar=False)
            return [emb.tolist() for emb in embeddings]
        except Exception as e:
            logger.error(f"Local embedding failed: {e}")
            return [[] for _ in texts]

    def _embed_api(self, texts: List[str]) -> List[List[float]]:
        """Fallback: use API-based embedding."""
        try:
            import httpx
            cfg = settings.embedding
            headers = {
                "Authorization": f"Bearer {cfg.api_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": "BAAI/bge-small-zh-v1.5",
                "input": texts,
            }
            with httpx.Client(timeout=30.0) as client:
                resp = client.post(
                    f"{cfg.api_base_url}/embeddings",
                    headers=headers,
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
                return [item["embedding"] for item in data["data"]]
        except Exception as e:
            logger.error(f"API embedding failed: {e}")
            return [[] for _ in texts]


# ---- Vector Search (Cosine Similarity - MVP) ----

def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0

    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))

    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def search_similar_chunks(
    query_embedding: List[float],
    chunks: List[TextChunk],
    top_k: int = 5,
) -> List[Tuple[TextChunk, float]]:
    """
    Find the top-k most similar chunks to a query embedding.
    Returns list of (chunk, similarity_score) tuples, sorted by score desc.
    """
    results: List[Tuple[TextChunk, float]] = []

    for chunk in chunks:
        if not chunk.embedding_json:
            continue
        try:
            chunk_emb = json.loads(chunk.embedding_json)
        except json.JSONDecodeError:
            continue

        score = cosine_similarity(query_embedding, chunk_emb)
        results.append((chunk, score))

    results.sort(key=lambda x: x[1], reverse=True)
    return results[:top_k]


# ---- High-Level Pipeline ----

def index_paper(file_path: str) -> List[TextChunk]:
    """
    Full indexing pipeline: extract → chunk → embed → return enriched chunks.
    Caller should save chunks to the database.
    """
    pages = extract_text_from_pdf(file_path)
    if not pages:
        return []

    chunks = chunk_text(pages)
    if not chunks:
        return []

    # Generate embeddings
    engine = EmbeddingEngine()
    texts = [c.text for c in chunks]
    embeddings = engine.embed_texts(texts)

    for chunk, emb in zip(chunks, embeddings):
        chunk.embedding_json = json.dumps(emb) if emb else ""

    logger.info(f"Paper indexed: {len(chunks)} chunks with embeddings.")
    return chunks
