"""
PaperMiner - Mine View
Paper discovery dashboard: search ArXiv/HuggingFace, AI recommendation agent.
"""

import logging
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QLabel,
    QPushButton, QLineEdit, QTableWidget, QTableWidgetItem,
    QHeaderView, QTextEdit, QComboBox, QGroupBox, QScrollArea,
    QMainWindow,
)
from PyQt6.QtCore import Qt

from core.database import DatabaseManager
from ui.components import SectionHeader, SearchBar

logger = logging.getLogger(__name__)


class MineView(QWidget):
    """Paper discovery view with search, source selection, and AI agent."""

    def __init__(self, db: DatabaseManager, main_window: "QMainWindow") -> None:
        super().__init__()
        self.db = db
        self.main_window = main_window
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Header
        header = QLabel("🔍 Mine Papers — Discover & Explore")
        header.setStyleSheet("""
            QLabel {
                color: #569CD6; font-size: 20px; font-weight: bold; padding-bottom: 8px;
            }
        """)
        layout.addWidget(header)

        # Search controls
        search_group = QGroupBox("Search Parameters")
        search_group.setStyleSheet("""
            QGroupBox {
                border: 1px solid #3C3C3C; border-radius: 6px;
                margin-top: 8px; padding-top: 16px;
                color: #9CDCFE; font-weight: bold;
            }
        """)
        sg_layout = QVBoxLayout(search_group)

        # Source + keyword row
        row1 = QHBoxLayout()

        self.source_selector = QComboBox()
        self.source_selector.addItems(["ArXiv", "HuggingFace Daily Papers", "Both"])
        self.source_selector.setFixedWidth(200)
        self.source_selector.setStyleSheet("""
            QComboBox {
                background: #3C3C3C; color: #D4D4D4; border: 1px solid #555;
                border-radius: 4px; padding: 6px 8px;
            }
        """)
        row1.addWidget(QLabel("Source:"))
        row1.addWidget(self.source_selector)

        self.keyword_input = QLineEdit()
        self.keyword_input.setPlaceholderText("Enter keywords: e.g. Transformer, LLM, Diffusion...")
        self.keyword_input.setStyleSheet("""
            QLineEdit {
                background: #1E1E1E; color: #D4D4D4; border: 1px solid #3C3C3C;
                border-radius: 6px; padding: 8px 12px; font-size: 14px;
            }
            QLineEdit:focus { border-color: #007ACC; }
        """)
        row1.addWidget(self.keyword_input, stretch=1)

        self.btn_search = QPushButton("🔎 Search")
        self.btn_search.setFixedWidth(100)
        self.btn_search.clicked.connect(self._on_search)
        row1.addWidget(self.btn_search)

        sg_layout.addLayout(row1)

        # Max results + sort
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Max results:"))
        self.max_results = QComboBox()
        self.max_results.addItems(["10", "25", "50", "100"])
        self.max_results.setFixedWidth(80)
        row2.addWidget(self.max_results)

        row2.addWidget(QLabel("Sort by:"))
        self.sort_selector = QComboBox()
        self.sort_selector.addItems(["Relevance", "Date (Newest)", "Date (Oldest)"])
        self.sort_selector.setFixedWidth(150)
        row2.addWidget(self.sort_selector)
        row2.addStretch()
        sg_layout.addLayout(row2)

        layout.addWidget(search_group)

        # Results area (splitter: table + detail/recommendation)
        results_splitter = QSplitter(Qt.Orientation.Horizontal)

        # Results table
        results_widget = QWidget()
        results_layout = QVBoxLayout(results_widget)
        results_layout.setContentsMargins(0, 0, 0, 0)
        results_layout.addWidget(SectionHeader("📄 SEARCH RESULTS"))

        self.results_table = QTableWidget(0, 4)
        self.results_table.setHorizontalHeaderLabels(["Title", "Authors", "Date", "Source"])
        self.results_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.results_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.results_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.results_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.results_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.results_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.results_table.setAlternatingRowColors(True)
        self.results_table.cellClicked.connect(self._on_result_clicked)
        results_layout.addWidget(self.results_table)

        # Detail panel
        detail_widget = QWidget()
        detail_layout = QVBoxLayout(detail_widget)
        detail_layout.setContentsMargins(8, 0, 0, 0)
        detail_layout.addWidget(SectionHeader("📋 PAPER DETAILS"))

        self.detail_view = QTextEdit()
        self.detail_view.setReadOnly(True)
        self.detail_view.setPlaceholderText("Select a paper from search results to see details...")
        detail_layout.addWidget(self.detail_view)

        btn_row = QHBoxLayout()
        self.btn_download = QPushButton("📥 Download to Library")
        self.btn_download.clicked.connect(self._download_paper)
        btn_row.addWidget(self.btn_download)

        self.btn_ai_summarize = QPushButton("🤖 AI Summarize")
        self.btn_ai_summarize.clicked.connect(self._ai_summarize)
        btn_row.addWidget(self.btn_ai_summarize)

        btn_row.addStretch()
        detail_layout.addLayout(btn_row)

        results_splitter.addWidget(results_widget)
        results_splitter.addWidget(detail_widget)
        results_splitter.setStretchFactor(0, 3)
        results_splitter.setStretchFactor(1, 2)

        layout.addWidget(results_splitter, stretch=1)

    def _on_search(self) -> None:
        """Trigger a search based on current parameters."""
        keyword = self.keyword_input.text().strip()
        if not keyword:
            return

        source = self.source_selector.currentText()
        max_results = int(self.max_results.currentText())

        self.main_window.show_status(f"Searching {source} for '{keyword}'...")
        logger.info(f"Search triggered: source={source}, keyword={keyword}, max={max_results}")

        # TODO: Connect to workers/async_workers → discovery/arxiv_client, hf_client
        # Placeholder: show mock results
        self.results_table.setRowCount(0)
        self.results_table.insertRow(0)
        self.results_table.setItem(0, 0, QTableWidgetItem(f"[Mock] {keyword} - Sample Paper"))
        self.results_table.setItem(0, 1, QTableWidgetItem("Author et al."))
        self.results_table.setItem(0, 2, QTableWidgetItem("2026-02-12"))
        self.results_table.setItem(0, 3, QTableWidgetItem(source))

        self.main_window.show_status(f"Search complete. (Discovery module not yet connected)", 3000)

    def _on_result_clicked(self, row: int, column: int) -> None:
        """Show details of the selected search result."""
        title_item = self.results_table.item(row, 0)
        if not title_item:
            return
        self.detail_view.setHtml(f"""
            <h3 style="color: #569CD6;">{title_item.text()}</h3>
            <p style="color: #808080;">Authors: {self.results_table.item(row, 1).text()}</p>
            <p style="color: #808080;">Date: {self.results_table.item(row, 2).text()}</p>
            <hr style="border-color: #3C3C3C;">
            <p style="color: #D4D4D4;">Abstract preview will appear here when connected to the search API.</p>
        """)

    def _download_paper(self) -> None:
        """Download the selected paper to the local library."""
        # TODO: Implement actual download logic
        self.main_window.show_status("Download feature not yet connected.", 3000)

    def _ai_summarize(self) -> None:
        """Ask AI to summarize the selected paper."""
        # TODO: Connect to AI sidebar / chat handler
        self.main_window.show_status("AI summarization not yet connected.", 3000)
