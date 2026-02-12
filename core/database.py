"""
PaperMiner - Database Manager
Handles all SQLite operations: folders, papers, annotations, notes, and text chunks.
"""

import sqlite3
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

from core.models import Folder, Paper, Annotation, Note, TextChunk

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Thread-safe SQLite database manager for PaperMiner."""

    def __init__(self, db_path: str = "library.db") -> None:
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.cursor = self.conn.cursor()
        self._create_tables()

    def _create_tables(self) -> None:
        """Create all required tables if they don't exist."""
        self.cursor.executescript("""
            CREATE TABLE IF NOT EXISTS folders (
                id   INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE
            );

            CREATE TABLE IF NOT EXISTS papers (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                title       TEXT NOT NULL,
                file_path   TEXT NOT NULL,
                folder_id   INTEGER,
                upload_date TEXT,
                abstract    TEXT DEFAULT '',
                authors     TEXT DEFAULT '',
                source_url  TEXT DEFAULT '',
                is_indexed  INTEGER DEFAULT 0,
                FOREIGN KEY (folder_id) REFERENCES folders(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS annotations (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                paper_id   INTEGER NOT NULL,
                page       INTEGER DEFAULT 0,
                content    TEXT DEFAULT '',
                comment    TEXT DEFAULT '',
                color      TEXT DEFAULT '#FFFF00',
                rects_json TEXT DEFAULT '[]',
                created_at TEXT,
                updated_at TEXT,
                FOREIGN KEY (paper_id) REFERENCES papers(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS notes (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                paper_id   INTEGER NOT NULL UNIQUE,
                content    TEXT DEFAULT '',
                updated_at TEXT,
                FOREIGN KEY (paper_id) REFERENCES papers(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS text_chunks (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                paper_id       INTEGER NOT NULL,
                chunk_index    INTEGER DEFAULT 0,
                text           TEXT DEFAULT '',
                embedding_json TEXT DEFAULT '',
                page_start     INTEGER DEFAULT 0,
                page_end       INTEGER DEFAULT 0,
                FOREIGN KEY (paper_id) REFERENCES papers(id) ON DELETE CASCADE
            );
        """)
        self.conn.commit()
        logger.info("Database tables initialized.")

    # ---- Folder Operations ----

    def add_folder(self, name: str) -> bool:
        """Add a new folder. Returns True on success, False if duplicate."""
        try:
            self.cursor.execute("INSERT INTO folders (name) VALUES (?)", (name,))
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def get_folders(self) -> List[Folder]:
        """Return all folders."""
        self.cursor.execute("SELECT id, name FROM folders ORDER BY name")
        return [Folder(id=r[0], name=r[1]) for r in self.cursor.fetchall()]

    def rename_folder(self, folder_id: int, new_name: str) -> bool:
        """Rename a folder."""
        try:
            self.cursor.execute("UPDATE folders SET name = ? WHERE id = ?", (new_name, folder_id))
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def delete_folder(self, folder_id: int) -> None:
        """Delete a folder (papers are kept with NULL folder_id)."""
        self.cursor.execute("DELETE FROM folders WHERE id = ?", (folder_id,))
        self.conn.commit()

    # ---- Paper Operations ----

    def add_paper(self, title: str, file_path: str, folder_id: int,
                  abstract: str = "", authors: str = "", source_url: str = "") -> int:
        """Add a paper and return its new ID."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.cursor.execute(
            """INSERT INTO papers (title, file_path, folder_id, upload_date,
               abstract, authors, source_url) VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (title, file_path, folder_id, now, abstract, authors, source_url),
        )
        self.conn.commit()
        return self.cursor.lastrowid  # type: ignore

    def get_papers_by_folder(self, folder_id: Optional[int] = None) -> List[Paper]:
        """Return papers in a folder, or all papers if folder_id is None."""
        if folder_id is None:
            self.cursor.execute("SELECT * FROM papers ORDER BY upload_date DESC")
        else:
            self.cursor.execute(
                "SELECT * FROM papers WHERE folder_id = ? ORDER BY upload_date DESC",
                (folder_id,),
            )
        return [self._row_to_paper(r) for r in self.cursor.fetchall()]

    def search_papers(self, keyword: str) -> List[Paper]:
        """Full-text keyword search on title, abstract, and authors."""
        q = f"%{keyword}%"
        self.cursor.execute(
            "SELECT * FROM papers WHERE title LIKE ? OR abstract LIKE ? OR authors LIKE ?",
            (q, q, q),
        )
        return [self._row_to_paper(r) for r in self.cursor.fetchall()]

    def delete_paper(self, paper_id: int) -> None:
        """Delete a paper and its associated data (cascade)."""
        self.cursor.execute("DELETE FROM papers WHERE id = ?", (paper_id,))
        self.conn.commit()

    def set_paper_indexed(self, paper_id: int, indexed: bool = True) -> None:
        """Mark a paper as indexed (embeddings generated)."""
        self.cursor.execute(
            "UPDATE papers SET is_indexed = ? WHERE id = ?", (int(indexed), paper_id)
        )
        self.conn.commit()

    def _row_to_paper(self, row: tuple) -> Paper:
        return Paper(
            id=row[0], title=row[1], file_path=row[2], folder_id=row[3],
            upload_date=row[4], abstract=row[5] or "", authors=row[6] or "",
            source_url=row[7] or "", is_indexed=bool(row[8]),
        )

    # ---- Annotation Operations ----

    def add_annotation(self, paper_id: int, page: int, content: str,
                       comment: str, color: str, rects_json: str) -> int:
        """Add a highlight annotation and return its ID."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.cursor.execute(
            """INSERT INTO annotations
               (paper_id, page, content, comment, color, rects_json, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (paper_id, page, content, comment, color, rects_json, now, now),
        )
        self.conn.commit()
        return self.cursor.lastrowid  # type: ignore

    def get_annotations(self, paper_id: int) -> List[Annotation]:
        """Return all annotations for a paper."""
        self.cursor.execute(
            "SELECT * FROM annotations WHERE paper_id = ? ORDER BY page, id", (paper_id,)
        )
        rows = self.cursor.fetchall()
        return [
            Annotation(
                id=r[0], paper_id=r[1], page=r[2], content=r[3],
                comment=r[4], color=r[5], rects_json=r[6],
                created_at=r[7] or "", updated_at=r[8] or "",
            )
            for r in rows
        ]

    def update_annotation_comment(self, annotation_id: int, comment: str) -> None:
        """Update the comment of an annotation."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.cursor.execute(
            "UPDATE annotations SET comment = ?, updated_at = ? WHERE id = ?",
            (comment, now, annotation_id),
        )
        self.conn.commit()

    def delete_annotation(self, annotation_id: int) -> None:
        """Delete a single annotation."""
        self.cursor.execute("DELETE FROM annotations WHERE id = ?", (annotation_id,))
        self.conn.commit()

    # ---- Note Operations ----

    def get_note(self, paper_id: int) -> str:
        """Return the note content for a paper, or empty string."""
        self.cursor.execute("SELECT content FROM notes WHERE paper_id = ?", (paper_id,))
        result = self.cursor.fetchone()
        return result[0] if result else ""

    def save_note(self, paper_id: int, content: str) -> None:
        """Insert or update the note for a paper."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.cursor.execute("SELECT id FROM notes WHERE paper_id = ?", (paper_id,))
        if self.cursor.fetchone():
            self.cursor.execute(
                "UPDATE notes SET content = ?, updated_at = ? WHERE paper_id = ?",
                (content, now, paper_id),
            )
        else:
            self.cursor.execute(
                "INSERT INTO notes (paper_id, content, updated_at) VALUES (?, ?, ?)",
                (paper_id, content, now),
            )
        self.conn.commit()

    # ---- Text Chunk Operations (for RAG) ----

    def save_chunks(self, paper_id: int, chunks: List[TextChunk]) -> None:
        """Bulk insert text chunks for a paper (clears existing ones first)."""
        self.cursor.execute("DELETE FROM text_chunks WHERE paper_id = ?", (paper_id,))
        for c in chunks:
            self.cursor.execute(
                """INSERT INTO text_chunks
                   (paper_id, chunk_index, text, embedding_json, page_start, page_end)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (paper_id, c.chunk_index, c.text, c.embedding_json,
                 c.page_start, c.page_end),
            )
        self.conn.commit()

    def get_chunks(self, paper_id: int) -> List[TextChunk]:
        """Return all text chunks for a paper."""
        self.cursor.execute(
            "SELECT * FROM text_chunks WHERE paper_id = ? ORDER BY chunk_index",
            (paper_id,),
        )
        return [
            TextChunk(
                id=r[0], paper_id=r[1], chunk_index=r[2], text=r[3],
                embedding_json=r[4], page_start=r[5], page_end=r[6],
            )
            for r in self.cursor.fetchall()
        ]

    def get_all_chunks(self) -> List[TextChunk]:
        """Return all text chunks across the entire library (for library-wide RAG)."""
        self.cursor.execute("SELECT * FROM text_chunks ORDER BY paper_id, chunk_index")
        return [
            TextChunk(
                id=r[0], paper_id=r[1], chunk_index=r[2], text=r[3],
                embedding_json=r[4], page_start=r[5], page_end=r[6],
            )
            for r in self.cursor.fetchall()
        ]

    def close(self) -> None:
        """Close the database connection."""
        self.conn.close()
