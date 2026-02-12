"""
PaperMiner - Manage View
The paper library management view: folder sidebar, paper list, PDF reader, and notes panel.
"""

import os
import shutil
import logging
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QListWidget,
    QTableWidget, QTableWidgetItem, QPushButton, QLabel, QFileDialog,
    QInputDialog, QMessageBox, QTextEdit, QHeaderView, QMenu, QListWidgetItem,
    QMainWindow,
)
from PyQt6.QtCore import Qt, QPoint

from config import LIBRARY_DIR
from core.database import DatabaseManager
from core.models import Paper
from ui.pdf_viewer import PDFViewerWidget
from ui.components import SectionHeader, SearchBar

logger = logging.getLogger(__name__)


class ManageView(QWidget):
    """Complete library management view with folders, paper list, reader, and notes."""

    def __init__(self, db: DatabaseManager, main_window: "QMainWindow") -> None:
        super().__init__()
        self.db = db
        self.main_window = main_window
        self.current_folder_id: Optional[int] = None
        self.current_paper_id: Optional[int] = None

        self._init_ui()
        self._load_folders()

    def _init_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setHandleWidth(1)

        # --- 1. Folder Sidebar ---
        self.folder_panel = self._build_folder_panel()

        # --- 2. Paper List ---
        self.paper_panel = self._build_paper_panel()

        # --- 3. Reader + Notes ---
        self.reader_panel = self._build_reader_panel()

        self.splitter.addWidget(self.folder_panel)
        self.splitter.addWidget(self.paper_panel)
        self.splitter.addWidget(self.reader_panel)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 2)
        self.splitter.setStretchFactor(2, 5)
        self.splitter.setSizes([180, 280, 800])

        layout.addWidget(self.splitter)

    # ---- Build Sub-Panels ----

    def _build_folder_panel(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        layout.addWidget(SectionHeader("📁 FOLDERS"))

        self.folder_list = QListWidget()
        self.folder_list.itemClicked.connect(self._on_folder_selected)
        self.folder_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.folder_list.customContextMenuRequested.connect(self._folder_context_menu)
        layout.addWidget(self.folder_list)

        btn_add_folder = QPushButton("+ New Folder")
        btn_add_folder.clicked.connect(self._add_new_folder)
        layout.addWidget(btn_add_folder)

        return w

    def _build_paper_panel(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        layout.addWidget(SectionHeader("📜 PAPERS"))

        # Search bar
        self.search_bar = SearchBar("Search papers...")
        self.search_bar.textChanged.connect(self._on_search)
        layout.addWidget(self.search_bar)

        # Paper table
        self.paper_table = QTableWidget(0, 3)
        self.paper_table.setHorizontalHeaderLabels(["Title", "Date", "Indexed"])
        self.paper_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.paper_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.paper_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.paper_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.paper_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.paper_table.setAlternatingRowColors(True)
        self.paper_table.cellClicked.connect(self._on_paper_selected)
        self.paper_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.paper_table.customContextMenuRequested.connect(self._paper_context_menu)
        layout.addWidget(self.paper_table)

        # Upload button
        btn_upload = QPushButton("📄 Upload PDF")
        btn_upload.clicked.connect(self._upload_paper)
        layout.addWidget(btn_upload)

        return w

    def _build_reader_panel(self) -> QWidget:
        reader_splitter = QSplitter(Qt.Orientation.Vertical)

        # PDF Viewer (PDF.js via QWebChannel)
        self.pdf_viewer = PDFViewerWidget(self.db, self)
        self.pdf_viewer.text_selected.connect(self._on_text_selected)
        self.pdf_viewer.annotation_saved.connect(self._on_annotation_saved)

        # Notes panel
        notes_widget = QWidget()
        notes_layout = QVBoxLayout(notes_widget)
        notes_layout.setContentsMargins(8, 4, 8, 8)
        notes_layout.addWidget(SectionHeader("📝 NOTES"))

        self.notes_editor = QTextEdit()
        self.notes_editor.setPlaceholderText("Capture your thoughts here...")
        self.notes_editor.textChanged.connect(self._auto_save_note)
        notes_layout.addWidget(self.notes_editor)

        reader_splitter.addWidget(self.pdf_viewer)
        reader_splitter.addWidget(notes_widget)
        reader_splitter.setStretchFactor(0, 4)
        reader_splitter.setStretchFactor(1, 1)

        return reader_splitter

    # ---- Folder Logic ----

    def _load_folders(self) -> None:
        self.folder_list.clear()
        all_item = QListWidgetItem("📂 All Papers")
        all_item.setData(Qt.ItemDataRole.UserRole, None)
        self.folder_list.addItem(all_item)

        for f in self.db.get_folders():
            item = QListWidgetItem(f"📁 {f.name}")
            item.setData(Qt.ItemDataRole.UserRole, f.id)
            self.folder_list.addItem(item)

    def _add_new_folder(self) -> None:
        name, ok = QInputDialog.getText(self, "New Folder", "Folder Name:")
        if ok and name.strip():
            if self.db.add_folder(name.strip()):
                self._load_folders()
                self.main_window.show_status(f"Folder '{name}' created.")
            else:
                QMessageBox.warning(self, "Error", "Folder already exists!")

    def _on_folder_selected(self, item: QListWidgetItem) -> None:
        self.current_folder_id = item.data(Qt.ItemDataRole.UserRole)
        self._refresh_paper_list()

    def _folder_context_menu(self, pos: QPoint) -> None:
        item = self.folder_list.itemAt(pos)
        if not item:
            return
        folder_id = item.data(Qt.ItemDataRole.UserRole)
        if folder_id is None:
            return  # "All Papers" not deletable

        menu = QMenu(self)
        rename_action = menu.addAction("Rename")
        delete_action = menu.addAction("Delete")

        action = menu.exec(self.folder_list.mapToGlobal(pos))
        if action == rename_action:
            new_name, ok = QInputDialog.getText(self, "Rename Folder", "New Name:")
            if ok and new_name.strip():
                self.db.rename_folder(folder_id, new_name.strip())
                self._load_folders()
        elif action == delete_action:
            confirm = QMessageBox.question(
                self, "Delete Folder",
                "Papers in this folder won't be deleted. Continue?",
            )
            if confirm == QMessageBox.StandardButton.Yes:
                self.db.delete_folder(folder_id)
                self._load_folders()
                self._refresh_paper_list()

    # ---- Paper Logic ----

    def _refresh_paper_list(self) -> None:
        self.paper_table.setRowCount(0)
        papers = self.db.get_papers_by_folder(self.current_folder_id)
        for p in papers:
            row = self.paper_table.rowCount()
            self.paper_table.insertRow(row)

            title_item = QTableWidgetItem(p.title)
            title_item.setData(Qt.ItemDataRole.UserRole, p)
            self.paper_table.setItem(row, 0, title_item)
            self.paper_table.setItem(row, 1, QTableWidgetItem(p.upload_date))
            self.paper_table.setItem(row, 2, QTableWidgetItem("✅" if p.is_indexed else "—"))

    def _on_search(self, keyword: str) -> None:
        if not keyword.strip():
            self._refresh_paper_list()
            return
        self.paper_table.setRowCount(0)
        papers = self.db.search_papers(keyword.strip())
        for p in papers:
            row = self.paper_table.rowCount()
            self.paper_table.insertRow(row)
            title_item = QTableWidgetItem(p.title)
            title_item.setData(Qt.ItemDataRole.UserRole, p)
            self.paper_table.setItem(row, 0, title_item)
            self.paper_table.setItem(row, 1, QTableWidgetItem(p.upload_date))
            self.paper_table.setItem(row, 2, QTableWidgetItem("✅" if p.is_indexed else "—"))

    def _on_paper_selected(self, row: int, column: int) -> None:
        item = self.paper_table.item(row, 0)
        if not item:
            return

        paper: Paper = item.data(Qt.ItemDataRole.UserRole)
        self.current_paper_id = paper.id
        file_path = paper.file_path

        logger.info(f"Loading paper: {paper.title} ({file_path})")

        if os.path.exists(file_path):
            self.pdf_viewer.load_pdf(file_path, paper.id)
            self.main_window.show_status(f"Opened: {paper.title}")
        else:
            QMessageBox.warning(self, "File Not Found", f"Missing: {file_path}")

        # Load notes
        note_content = self.db.get_note(paper.id)
        self.notes_editor.blockSignals(True)
        self.notes_editor.setPlainText(note_content)
        self.notes_editor.blockSignals(False)

    def _paper_context_menu(self, pos: QPoint) -> None:
        item = self.paper_table.itemAt(pos)
        if not item:
            return
        paper: Paper = self.paper_table.item(item.row(), 0).data(Qt.ItemDataRole.UserRole)

        menu = QMenu(self)
        index_action = menu.addAction("🔗 Index for RAG")
        delete_action = menu.addAction("🗑 Delete")

        action = menu.exec(self.paper_table.mapToGlobal(pos))
        if action == index_action:
            self._index_paper(paper)
        elif action == delete_action:
            confirm = QMessageBox.question(self, "Delete Paper", f"Delete '{paper.title}'?")
            if confirm == QMessageBox.StandardButton.Yes:
                self.db.delete_paper(paper.id)
                self._refresh_paper_list()

    def _upload_paper(self) -> None:
        if self.current_folder_id is None:
            QMessageBox.information(self, "Info", "Please select a folder first!")
            return

        file_path, _ = QFileDialog.getOpenFileName(self, "Select PDF", "", "PDF Files (*.pdf)")
        if not file_path:
            return

        filename = os.path.basename(file_path)
        dest_path = LIBRARY_DIR / filename
        try:
            shutil.copy2(file_path, dest_path)
            paper_id = self.db.add_paper(filename, str(dest_path.absolute()), self.current_folder_id)
            self._refresh_paper_list()
            self.main_window.show_status(f"Uploaded: {filename}")
            logger.info(f"Paper uploaded: {filename} -> {dest_path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Upload failed: {e}")
            logger.error(f"Upload failed: {e}")

    def _index_paper(self, paper: Paper) -> None:
        """Trigger RAG indexing for a paper (runs in background thread)."""
        # TODO: Connect to workers/async_workers.py → RAG engine
        self.main_window.show_status(f"Indexing '{paper.title}'... (not yet implemented)")
        logger.info(f"Indexing requested for paper_id={paper.id}")

    # ---- Notes Logic ----

    def _auto_save_note(self) -> None:
        if self.current_paper_id:
            content = self.notes_editor.toPlainText()
            self.db.save_note(self.current_paper_id, content)

    # ---- Callbacks from PDF Viewer ----

    def _on_text_selected(self, selected_text: str) -> None:
        """Handle text selection in the PDF viewer - show contextual actions."""
        logger.debug(f"Text selected in PDF: {selected_text[:80]}...")
        # The floating menu is handled inside PDFViewerWidget via JS
        # This signal is for potential Python-side usage

    def _on_annotation_saved(self, annotation_id: int) -> None:
        """Handle annotation saved callback from PDF viewer."""
        self.main_window.show_status("Annotation saved.", 2000)
