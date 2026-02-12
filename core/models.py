"""
PaperMiner - Data Models
Dataclass definitions for Papers, Folders, Annotations, and Chunks.
"""

from dataclasses import dataclass, field
from typing import Optional, List
from datetime import datetime


@dataclass
class Folder:
    """Represents a paper folder/category."""
    id: Optional[int] = None
    name: str = ""


@dataclass
class Paper:
    """Represents a single paper entry."""
    id: Optional[int] = None
    title: str = ""
    file_path: str = ""
    folder_id: Optional[int] = None
    upload_date: str = ""
    abstract: str = ""
    authors: str = ""
    source_url: str = ""          # ArXiv / HuggingFace link
    is_indexed: bool = False      # Whether embeddings have been generated


@dataclass
class Annotation:
    """Represents a highlight / comment annotation on a PDF."""
    id: Optional[int] = None
    paper_id: Optional[int] = None
    page: int = 0                 # 0-indexed page number
    content: str = ""             # The highlighted text
    comment: str = ""             # User's comment on the highlight
    color: str = "#FFFF00"        # Highlight color hex
    rects_json: str = "[]"        # JSON-serialized list of {x, y, w, h} rects
    created_at: str = ""
    updated_at: str = ""


@dataclass
class Note:
    """Represents a free-form note attached to a paper."""
    id: Optional[int] = None
    paper_id: Optional[int] = None
    content: str = ""
    updated_at: str = ""


@dataclass
class TextChunk:
    """Represents a text chunk from a paper, used for RAG."""
    id: Optional[int] = None
    paper_id: Optional[int] = None
    chunk_index: int = 0
    text: str = ""
    embedding_json: str = ""     # JSON-serialized float list (or empty if using FAISS)
    page_start: int = 0
    page_end: int = 0


@dataclass
class ChatMessage:
    """Represents a single message in a chat session."""
    role: str = "user"           # user | assistant | system
    content: str = ""
    timestamp: str = ""
    sources: List[str] = field(default_factory=list)  # chunk references
