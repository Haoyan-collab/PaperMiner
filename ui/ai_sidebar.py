"""
PaperMiner - AI Chat Sidebar
Collapsible right-side panel for AI-powered interactions:
  - Chat with current paper (RAG)
  - Chat with full library
  - Contextual actions (Explain, Translate)
"""

import logging
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QLineEdit,
    QPushButton, QLabel, QComboBox, QScrollArea, QFrame,
)
from PyQt6.QtCore import Qt, pyqtSignal

from core.database import DatabaseManager

logger = logging.getLogger(__name__)


class ChatBubble(QFrame):
    """A single chat message bubble."""

    def __init__(self, role: str, content: str, parent: QWidget = None) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)

        is_user = role == "user"
        bg_color = "#264F78" if is_user else "#2D2D2D"
        align = "right" if is_user else "left"

        self.setStyleSheet(f"""
            QFrame {{
                background-color: {bg_color};
                border-radius: 8px;
                border: none;
                margin: 2px {'2px 2px 40px' if is_user else '40px 2px 2px'};
            }}
        """)

        role_label = QLabel("🧑 You" if is_user else "🤖 AI")
        role_label.setStyleSheet("color: #808080; font-size: 11px; font-weight: bold;")
        layout.addWidget(role_label)

        text_label = QLabel(content)
        text_label.setWordWrap(True)
        text_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        text_label.setStyleSheet("color: #D4D4D4; font-size: 13px; padding: 2px;")
        layout.addWidget(text_label)


class AISidebar(QWidget):
    """Collapsible AI chat sidebar with mode switching."""

    message_sent = pyqtSignal(str, str)  # (mode, message)

    def __init__(self, db: DatabaseManager, parent: QWidget = None) -> None:
        super().__init__(parent)
        self.db = db
        self.setMinimumWidth(300)
        self.setMaximumWidth(500)

        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header bar
        header = QWidget()
        header.setStyleSheet("background-color: #252526; border-bottom: 1px solid #3C3C3C;")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 8, 12, 8)

        title = QLabel("🤖 AI Assistant")
        title.setStyleSheet("color: #569CD6; font-size: 14px; font-weight: bold;")
        header_layout.addWidget(title)

        header_layout.addStretch()

        # Mode selector
        self.mode_selector = QComboBox()
        self.mode_selector.addItems(["Chat with Paper", "Chat with Library", "Free Chat"])
        self.mode_selector.setStyleSheet("""
            QComboBox {
                background: #3C3C3C; color: #D4D4D4; border: 1px solid #555;
                border-radius: 4px; padding: 4px 8px; font-size: 12px;
            }
            QComboBox::drop-down { border: none; }
            QComboBox QAbstractItemView {
                background: #252526; color: #D4D4D4; selection-background-color: #094771;
            }
        """)
        header_layout.addWidget(self.mode_selector)

        layout.addWidget(header)

        # Chat history area (scrollable)
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("QScrollArea { border: none; background: #1E1E1E; }")

        self.chat_container = QWidget()
        self.chat_layout = QVBoxLayout(self.chat_container)
        self.chat_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.chat_layout.setContentsMargins(8, 8, 8, 8)
        self.chat_layout.setSpacing(6)

        self.scroll_area.setWidget(self.chat_container)
        layout.addWidget(self.scroll_area, stretch=1)

        # Input area
        input_widget = QWidget()
        input_widget.setStyleSheet("background-color: #252526; border-top: 1px solid #3C3C3C;")
        input_layout = QVBoxLayout(input_widget)
        input_layout.setContentsMargins(8, 8, 8, 8)
        input_layout.setSpacing(6)

        self.input_box = QTextEdit()
        self.input_box.setPlaceholderText("Ask anything about your papers...")
        self.input_box.setMaximumHeight(80)
        self.input_box.setStyleSheet("""
            QTextEdit {
                background: #1E1E1E; color: #D4D4D4;
                border: 1px solid #3C3C3C; border-radius: 6px;
                padding: 6px; font-size: 13px;
            }
            QTextEdit:focus { border-color: #007ACC; }
        """)
        input_layout.addWidget(self.input_box)

        btn_row = QHBoxLayout()
        self.btn_send = QPushButton("Send ⏎")
        self.btn_send.clicked.connect(self._on_send)
        self.btn_send.setStyleSheet("""
            QPushButton {
                background: #0E639C; color: white; border: none;
                border-radius: 4px; padding: 6px 20px; font-size: 13px;
            }
            QPushButton:hover { background: #1177BB; }
        """)
        btn_row.addStretch()

        self.btn_clear = QPushButton("Clear")
        self.btn_clear.clicked.connect(self._clear_chat)
        self.btn_clear.setStyleSheet("""
            QPushButton {
                background: transparent; color: #808080; border: 1px solid #3C3C3C;
                border-radius: 4px; padding: 6px 12px; font-size: 12px;
            }
            QPushButton:hover { color: #D4D4D4; border-color: #555; }
        """)
        btn_row.addWidget(self.btn_clear)
        btn_row.addWidget(self.btn_send)
        input_layout.addLayout(btn_row)

        layout.addWidget(input_widget)

        # Welcome message
        self._add_bubble("assistant", "Hi! I'm your AI research assistant. Select a chat mode above and ask me anything about your papers.")

    def _on_send(self) -> None:
        text = self.input_box.toPlainText().strip()
        if not text:
            return

        self._add_bubble("user", text)
        self.input_box.clear()

        mode = self.mode_selector.currentText()
        self.message_sent.emit(mode, text)

        # TODO: Connect to workers/async_workers → AI chat handler
        # For now, placeholder response
        self._add_bubble("assistant", f"[{mode}] Thinking... (AI backend not yet connected)")

    def _add_bubble(self, role: str, content: str) -> None:
        bubble = ChatBubble(role, content)
        self.chat_layout.addWidget(bubble)
        # Auto-scroll to bottom
        self.scroll_area.verticalScrollBar().setValue(
            self.scroll_area.verticalScrollBar().maximum()
        )

    def add_ai_response(self, content: str) -> None:
        """Public method for workers to push AI responses."""
        self._add_bubble("assistant", content)

    def set_context(self, text: str, action: str) -> None:
        """Pre-fill the input with a contextual action from the PDF viewer."""
        action_prompts = {
            "explain": f"Please explain the following text from my paper:\n\n\"{text}\"",
            "translate": f"Please translate the following text to Chinese, preserving academic context:\n\n\"{text}\"",
            "save_to_notes": None,  # Handled differently
        }

        prompt = action_prompts.get(action)
        if prompt:
            self.input_box.setPlainText(prompt)
            self.input_box.setFocus()
        elif action == "save_to_notes":
            # Signal the manage view to save to notes
            main_win = self.window()
            if hasattr(main_win, "manage_view"):
                editor = main_win.manage_view.notes_editor
                current = editor.toPlainText()
                separator = "\n\n---\n\n" if current else ""
                editor.setPlainText(current + separator + text)
                self._add_bubble("assistant", "Text saved to your notes.")

    def _clear_chat(self) -> None:
        """Clear all chat bubbles."""
        while self.chat_layout.count():
            child = self.chat_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self._add_bubble("assistant", "Chat cleared. How can I help?")
