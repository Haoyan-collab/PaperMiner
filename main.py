"""
PaperMiner - Entry Point
AI-Powered Paper Research Assistant

Sets up environment, configures logging, and launches the main window.
"""

import sys
import os
import logging

# --- Critical Environment Setup (must be before any Qt imports) ---
# Fixes Win11 GPU/sandbox issues with QWebEngine rendering local PDFs
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = (
    "--disable-gpu --allow-file-access-from-files --no-sandbox"
)
os.environ["QTWEBENGINE_DISABLE_SANDBOX"] = "1"

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtWebEngineCore import QWebEngineUrlScheme

# --- Register custom URL scheme BEFORE QApplication is created ---
# Qt requires schemes to be registered before the QApplication instance exists.
_local_scheme = QWebEngineUrlScheme(b"local")
_local_scheme.setSyntax(QWebEngineUrlScheme.Syntax.Host)
_local_scheme.setFlags(
    QWebEngineUrlScheme.Flag.SecureScheme
    | QWebEngineUrlScheme.Flag.LocalAccessAllowed
    | QWebEngineUrlScheme.Flag.CorsEnabled
    | QWebEngineUrlScheme.Flag.ContentSecurityPolicyIgnored
)
QWebEngineUrlScheme.registerScheme(_local_scheme)

from config import settings, APP_ROOT
from ui.main_window import MainWindow


def setup_logging() -> None:
    """Configure application-wide logging."""
    log_format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    logging.basicConfig(
        level=logging.DEBUG,
        format=log_format,
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(APP_ROOT / "paperminer.log", encoding="utf-8"),
        ],
    )
    # Suppress noisy libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def main() -> None:
    """Application entry point."""
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("PaperMiner starting...")
    logger.info(f"App root: {APP_ROOT}")
    logger.info(f"LLM provider: {settings.llm.provider} / {settings.llm.model_name}")

    app = QApplication(sys.argv)
    app.setApplicationName("PaperMiner")
    app.setOrganizationName("PaperMiner")

    window = MainWindow()
    window.show()

    logger.info("Main window displayed.")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()