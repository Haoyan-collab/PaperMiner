"""
PaperMiner - Main Window
Central hub with sidebar navigation switching between Manage / Mine views,
plus a collapsible AI chat sidebar on the right.
"""

import logging
from typing import Optional

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget,
    QSplitter, QStatusBar, QLabel, QSizePolicy, QApplication,
)
from PyQt6.QtCore import Qt, QSize

from config import settings, DB_PATH
from core.database import DatabaseManager
from ui.components import NavButton, Separator, SectionHeader, GLOBAL_STYLESHEET
from ui.manage_view import ManageView
from ui.mine_view import MineView
from ui.ai_sidebar import AISidebar

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Top-level application window with sidebar navigation."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("PaperMiner - AI Paper Research Assistant")
        self.resize(1500, 950)
        self.setMinimumSize(QSize(1000, 600))

        # Apply global dark theme
        self.setStyleSheet(GLOBAL_STYLESHEET)

        # Database
        self.db = DatabaseManager(str(DB_PATH))

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("PaperMiner Ready")

        # Build UI
        self._init_ui()

        # Default to Manage view
        self._switch_view(0)

    def _init_ui(self) -> None:
        """Construct the three-column layout: NavBar | Content | AI Sidebar."""
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # --- 1. Left Navigation Bar (fixed width) ---
        self.nav_bar = self._build_nav_bar()
        root_layout.addWidget(self.nav_bar)

        # --- 2. Main Content Area (QStackedWidget) ---
        self.content_stack = QStackedWidget()

        self.manage_view = ManageView(self.db, self)
        self.mine_view = MineView(self.db, self)

        self.content_stack.addWidget(self.manage_view)   # index 0
        self.content_stack.addWidget(self.mine_view)     # index 1

        # --- 3. AI Sidebar (collapsible) ---
        self.ai_sidebar = AISidebar(self.db, self)

        # Use a splitter for content + AI sidebar
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.main_splitter.setHandleWidth(1)
        self.main_splitter.addWidget(self.content_stack)
        self.main_splitter.addWidget(self.ai_sidebar)
        self.main_splitter.setStretchFactor(0, 4)
        self.main_splitter.setStretchFactor(1, 1)

        # Start with AI sidebar collapsed
        self.ai_sidebar.setVisible(False)

        root_layout.addWidget(self.main_splitter, stretch=1)

    def _build_nav_bar(self) -> QWidget:
        """Build the fixed-width left sidebar with navigation buttons."""
        nav = QWidget()
        nav.setFixedWidth(200)
        nav.setStyleSheet("background-color: #252526; border-right: 1px solid #3C3C3C;")

        layout = QVBoxLayout(nav)
        layout.setContentsMargins(8, 12, 8, 12)
        layout.setSpacing(4)

        # App title
        title = QLabel("📘 PaperMiner")
        title.setStyleSheet("""
            QLabel {
                color: #569CD6;
                font-size: 16px;
                font-weight: bold;
                padding: 8px 4px 16px 4px;
            }
        """)
        layout.addWidget(title)

        # Navigation section
        layout.addWidget(SectionHeader("WORKSPACE"))

        self.btn_manage = NavButton("Manage Papers", "📚")
        self.btn_manage.setChecked(True)
        self.btn_manage.clicked.connect(lambda: self._switch_view(0))

        self.btn_mine = NavButton("Mine Papers", "🔍")
        self.btn_mine.clicked.connect(lambda: self._switch_view(1))

        layout.addWidget(self.btn_manage)
        layout.addWidget(self.btn_mine)

        layout.addWidget(Separator())
        layout.addWidget(SectionHeader("TOOLS"))

        self.btn_ai_toggle = NavButton("AI Assistant", "🤖")
        self.btn_ai_toggle.setCheckable(True)
        self.btn_ai_toggle.clicked.connect(self._toggle_ai_sidebar)
        layout.addWidget(self.btn_ai_toggle)

        # Spacer
        layout.addStretch()

        # Settings button at bottom
        layout.addWidget(Separator())
        self.btn_settings = NavButton("Settings", "⚙️")
        self.btn_settings.clicked.connect(self._open_settings)
        layout.addWidget(self.btn_settings)

        return nav

    def _switch_view(self, index: int) -> None:
        """Switch the stacked widget to the given view index."""
        self.content_stack.setCurrentIndex(index)

        # Update button states
        self.btn_manage.setChecked(index == 0)
        self.btn_mine.setChecked(index == 1)

        view_names = {0: "Manage Papers", 1: "Mine Papers"}
        self.status_bar.showMessage(f"View: {view_names.get(index, 'Unknown')}")
        logger.info(f"Switched to view: {view_names.get(index)}")

    def _toggle_ai_sidebar(self) -> None:
        """Show or hide the AI chat sidebar."""
        visible = not self.ai_sidebar.isVisible()
        self.ai_sidebar.setVisible(visible)
        self.btn_ai_toggle.setChecked(visible)

        if visible:
            # Restore splitter sizes: ~75% content, ~25% AI
            total = self.main_splitter.width()
            self.main_splitter.setSizes([int(total * 0.75), int(total * 0.25)])

        logger.info(f"AI Sidebar visible: {visible}")

    def _open_settings(self) -> None:
        """Open settings dialog (placeholder for future implementation)."""
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.information(
            self, "Settings",
            "Settings dialog will be implemented here.\n"
            f"Current LLM: {settings.llm.provider} / {settings.llm.model_name}"
        )

    def show_status(self, message: str, timeout: int = 3000) -> None:
        """Convenience method for child widgets to update status bar."""
        self.status_bar.showMessage(message, timeout)

    def open_ai_with_context(self, context_text: str, action: str = "explain") -> None:
        """Open the AI sidebar with pre-filled context (for contextual actions)."""
        if not self.ai_sidebar.isVisible():
            self._toggle_ai_sidebar()
        self.ai_sidebar.set_context(context_text, action)

    def closeEvent(self, event) -> None:
        """Clean up resources on exit."""
        self.db.close()
        settings.save()
        logger.info("Application closed.")
        super().closeEvent(event)
