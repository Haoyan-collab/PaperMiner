"""
PaperMiner - Reusable UI Components
Shared widgets: NavigationButton, CollapsibleSection, SearchBar, etc.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QLineEdit, QFrame, QSizePolicy,
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QIcon, QFont


class NavButton(QPushButton):
    """A sidebar navigation button with icon + label, toggleable active state."""

    def __init__(self, text: str, icon_char: str = "", parent: QWidget = None) -> None:
        super().__init__(parent)
        self.setText(f"  {icon_char}  {text}" if icon_char else f"  {text}")
        self.setCheckable(True)
        self.setFixedHeight(44)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        font = QFont()
        font.setPointSize(11)
        self.setFont(font)
        self.setStyleSheet(self._style())

    @staticmethod
    def _style() -> str:
        return """
            QPushButton {
                text-align: left;
                border: none;
                border-radius: 6px;
                padding-left: 12px;
                color: #D4D4D4;
                background: transparent;
            }
            QPushButton:hover {
                background: #2A2D2E;
            }
            QPushButton:checked {
                background: #37373D;
                color: #FFFFFF;
                font-weight: bold;
            }
        """


class SearchBar(QWidget):
    """A search bar with a clear button, emitting textChanged signal."""
    textChanged = pyqtSignal(str)

    def __init__(self, placeholder: str = "Search...", parent: QWidget = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.input = QLineEdit()
        self.input.setPlaceholderText(placeholder)
        self.input.setStyleSheet("""
            QLineEdit {
                border: 1px solid #3C3C3C;
                border-radius: 6px;
                padding: 6px 10px;
                background: #1E1E1E;
                color: #CCCCCC;
                font-size: 13px;
            }
            QLineEdit:focus { border-color: #007ACC; }
        """)
        self.input.textChanged.connect(self.textChanged.emit)
        layout.addWidget(self.input)

        self.btn_clear = QPushButton("✕")
        self.btn_clear.setFixedSize(28, 28)
        self.btn_clear.setStyleSheet("""
            QPushButton {
                border: none; background: transparent; color: #808080; font-size: 14px;
            }
            QPushButton:hover { color: #FFFFFF; }
        """)
        self.btn_clear.clicked.connect(lambda: self.input.clear())
        layout.addWidget(self.btn_clear)

    def text(self) -> str:
        return self.input.text()


class Separator(QFrame):
    """A horizontal line separator."""

    def __init__(self, parent: QWidget = None) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.HLine)
        self.setStyleSheet("color: #3C3C3C;")
        self.setFixedHeight(1)


class SectionHeader(QLabel):
    """A styled section header label."""

    def __init__(self, text: str, parent: QWidget = None) -> None:
        super().__init__(text, parent)
        self.setStyleSheet("""
            QLabel {
                color: #9CDCFE;
                font-size: 11px;
                font-weight: bold;
                padding: 8px 12px 4px 12px;
                text-transform: uppercase;
                letter-spacing: 1px;
            }
        """)


GLOBAL_STYLESHEET = """
    QMainWindow, QWidget {
        background-color: #1E1E1E;
        color: #D4D4D4;
        font-family: "Segoe UI", "Microsoft YaHei UI", sans-serif;
    }
    QSplitter::handle {
        background-color: #3C3C3C;
        width: 1px;
    }
    QTableWidget {
        background-color: #1E1E1E;
        alternate-background-color: #252526;
        border: 1px solid #3C3C3C;
        gridline-color: #2D2D2D;
        color: #D4D4D4;
        selection-background-color: #264F78;
        selection-color: #FFFFFF;
        font-size: 13px;
    }
    QTableWidget::item { padding: 4px; }
    QHeaderView::section {
        background-color: #252526;
        color: #D4D4D4;
        border: none;
        border-bottom: 1px solid #3C3C3C;
        padding: 6px;
        font-weight: bold;
    }
    QListWidget {
        background-color: #1E1E1E;
        border: 1px solid #3C3C3C;
        color: #D4D4D4;
        font-size: 13px;
    }
    QListWidget::item {
        padding: 6px 10px;
        border-radius: 4px;
    }
    QListWidget::item:selected {
        background-color: #264F78;
        color: #FFFFFF;
    }
    QListWidget::item:hover {
        background-color: #2A2D2E;
    }
    QPushButton {
        background-color: #0E639C;
        color: #FFFFFF;
        border: none;
        border-radius: 4px;
        padding: 6px 16px;
        font-size: 13px;
    }
    QPushButton:hover { background-color: #1177BB; }
    QPushButton:pressed { background-color: #094771; }
    QPushButton:disabled { background-color: #3C3C3C; color: #6C6C6C; }
    QTextEdit {
        background-color: #1E1E1E;
        color: #D4D4D4;
        border: 1px solid #3C3C3C;
        border-radius: 4px;
        font-size: 13px;
        padding: 6px;
    }
    QTextEdit:focus { border-color: #007ACC; }
    QStatusBar {
        background-color: #007ACC;
        color: #FFFFFF;
        font-size: 12px;
    }
    QMenu {
        background-color: #252526;
        border: 1px solid #3C3C3C;
        color: #D4D4D4;
        padding: 4px;
    }
    QMenu::item:selected { background-color: #094771; }
    QScrollBar:vertical {
        background: #1E1E1E; width: 10px; margin: 0;
    }
    QScrollBar::handle:vertical {
        background: #424242; min-height: 30px; border-radius: 5px;
    }
    QScrollBar::handle:vertical:hover { background: #4F4F4F; }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
"""
