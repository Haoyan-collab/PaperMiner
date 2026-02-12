"""
PaperMiner - PDF Viewer Widget
Wraps PDF.js inside QWebEngineView with QWebChannel bridge for:
  - Loading local PDFs via PDF.js viewer
  - Bidirectional Python ↔ JavaScript communication
  - Text selection with contextual action menus
  - Annotation highlighting (save/load from SQLite)
"""

import json
import logging
import os
from pathlib import Path
from typing import Optional, List

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QMenu,
)
from PyQt6.QtCore import Qt, QUrl, QByteArray, QBuffer, QIODevice, pyqtSignal, pyqtSlot, QObject
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import (
    QWebEnginePage, QWebEngineSettings, QWebEngineUrlSchemeHandler, QWebEngineProfile
)
from PyQt6.QtWebChannel import QWebChannel

from config import PDFJS_DIR, RESOURCES_DIR
from core.database import DatabaseManager
from core.models import Annotation

logger = logging.getLogger(__name__)


class LocalFileSchemeHandler(QWebEngineUrlSchemeHandler):
    """Custom URL scheme handler for loading local PDF files."""

    # MIME type map for common extensions
    _MIME_TYPES = {
        ".pdf": b"application/pdf",
        ".html": b"text/html",
        ".js": b"application/javascript",
        ".mjs": b"application/javascript",
        ".css": b"text/css",
        ".json": b"application/json",
        ".wasm": b"application/wasm",
        ".svg": b"image/svg+xml",
        ".png": b"image/png",
        ".jpg": b"image/jpeg",
        ".jpeg": b"image/jpeg",
        ".gif": b"image/gif",
        ".woff2": b"font/woff2",
        ".woff": b"font/woff",
        ".ttf": b"font/ttf",
        ".bcmap": b"application/octet-stream",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        # prevent Python GC from destroying buffers still in use by Chromium
        self._active_buffers: list = []

    def requestStarted(self, request):
        """Handle requests for local:// URLs."""
        url = request.requestUrl()

        # Extract file path from the full URL string to avoid Qt's
        # Host-syntax URL parsing dropping the Windows drive letter.
        raw = url.toString()
        path = raw.split("?", 1)[0]            # strip query string
        path = path.replace("local://", "", 1)  # strip scheme
        # Remove leading slash for Windows paths like /E:/...
        if path.startswith("/") and len(path) > 2 and path[2] == ":":
            path = path[1:]

        logger.debug(f"LocalFileSchemeHandler: Loading {path}")

        try:
            with open(path, "rb") as f:
                data = f.read()

            # Determine MIME type
            ext = os.path.splitext(path)[1].lower()
            mime_type = self._MIME_TYPES.get(ext, b"application/octet-stream")

            # Build a self-contained QBuffer so Python GC cannot
            # destroy the backing QByteArray while Chromium reads it.
            buf = QBuffer(request)
            buf.open(QIODevice.OpenModeFlag.ReadWrite)
            buf.write(data)
            buf.seek(0)

            # Hold a Python reference until the request is destroyed
            self._active_buffers.append(buf)
            request.destroyed.connect(lambda b=buf: self._release_buffer(b))

            request.reply(mime_type, buf)
            logger.debug(f"Successfully loaded {len(data)} bytes from {path}")
        except Exception as e:
            logger.error(f"Failed to load {path}: {e}")
            request.fail(request.Error.UrlNotFound)

    def _release_buffer(self, buf):
        """Remove buffer reference once the request is finished."""
        try:
            self._active_buffers.remove(buf)
        except ValueError:
            pass


class JsBridge(QObject):
    """
    Python ↔ JavaScript bridge object, exposed to the web page via QWebChannel.
    JavaScript calls methods on this object; Python emits signals back.
    """

    # Signals emitted when JS sends data to Python
    text_selected = pyqtSignal(str)              # Selected text content
    annotation_request = pyqtSignal(str)         # JSON: {page, text, rects, color}
    context_action = pyqtSignal(str, str)        # (action_type, selected_text)
    viewer_ready = pyqtSignal()                  # PDF.js viewer has finished loading
    page_changed = pyqtSignal(int)               # Current page number changed

    def __init__(self, parent: QObject = None) -> None:
        super().__init__(parent)

    @pyqtSlot(str)
    def onTextSelected(self, text: str) -> None:
        """Called by JS when user selects text in the PDF."""
        logger.debug(f"JS → Python: text selected ({len(text)} chars)")
        self.text_selected.emit(text)

    @pyqtSlot(str)
    def onAnnotationRequest(self, data_json: str) -> None:
        """Called by JS when user creates a highlight annotation."""
        logger.debug(f"JS → Python: annotation request")
        self.annotation_request.emit(data_json)

    @pyqtSlot(str, str)
    def onContextAction(self, action: str, text: str) -> None:
        """Called by JS when user clicks a contextual action (Explain/Translate/Save)."""
        logger.info(f"JS → Python: context action '{action}' on text ({len(text)} chars)")
        self.context_action.emit(action, text)

    @pyqtSlot()
    def onViewerReady(self) -> None:
        """Called by JS when the PDF.js viewer is fully initialized."""
        logger.info("JS → Python: PDF.js viewer ready")
        self.viewer_ready.emit()

    @pyqtSlot(int)
    def onPageChanged(self, page_num: int) -> None:
        """Called by JS when user navigates to a different page."""
        self.page_changed.emit(page_num)


class PDFViewerWidget(QWidget):
    """
    A QWidget wrapping QWebEngineView that loads PDF.js with QWebChannel integration.
    Provides annotation management and contextual text actions.
    """

    # Signals for parent widgets
    text_selected = pyqtSignal(str)
    annotation_saved = pyqtSignal(int)  # annotation_id

    def __init__(self, db: DatabaseManager, parent: QWidget = None) -> None:
        super().__init__(parent)
        self.db = db
        self.current_paper_id: Optional[int] = None
        self.current_pdf_path: Optional[str] = None
        self._viewer_ready = False

        self._init_ui()
        self._setup_scheme_handler()
        self._setup_bridge()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(4, 4, 4, 4)

        self.btn_refresh = QPushButton("🔄 Refresh")
        self.btn_refresh.setFixedWidth(90)
        self.btn_refresh.clicked.connect(self._refresh_pdf)
        toolbar.addWidget(self.btn_refresh)

        self.btn_zoom_in = QPushButton("🔍+")
        self.btn_zoom_in.setFixedWidth(50)
        self.btn_zoom_in.clicked.connect(lambda: self._run_js("PDFViewerApplication.pdfViewer.currentScale *= 1.1"))
        toolbar.addWidget(self.btn_zoom_in)

        self.btn_zoom_out = QPushButton("🔍−")
        self.btn_zoom_out.setFixedWidth(50)
        self.btn_zoom_out.clicked.connect(lambda: self._run_js("PDFViewerApplication.pdfViewer.currentScale /= 1.1"))
        toolbar.addWidget(self.btn_zoom_out)

        toolbar.addStretch()

        self.page_label = QPushButton("Page: —")
        self.page_label.setFlat(True)
        self.page_label.setStyleSheet("color: #808080; border: none; font-size: 12px;")
        toolbar.addWidget(self.page_label)

        layout.addLayout(toolbar)

        # WebEngine view for PDF.js
        self.web_view = QWebEngineView()
        self._configure_web_settings()
        
        # Enable right-click context menu with "Inspect" option for debugging
        self.web_view.page().setDevToolsPage(QWebEnginePage(self.web_view))
        
        layout.addWidget(self.web_view)

    def _configure_web_settings(self) -> None:
        """Apply necessary QWebEngine settings for local PDF.js rendering."""
        s = self.web_view.settings()
        s.setAttribute(QWebEngineSettings.WebAttribute.PluginsEnabled, True)
        s.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
        s.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        s.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        s.setAttribute(QWebEngineSettings.WebAttribute.ScrollAnimatorEnabled, True)
        # Disable the built-in PDF viewer to force our PDF.js
        s.setAttribute(QWebEngineSettings.WebAttribute.PdfViewerEnabled, False)
        # Enable dev tools for debugging
        s.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows, True)

    def _setup_scheme_handler(self) -> None:
        """Register custom URL scheme handler for local files."""
        profile = QWebEngineProfile.defaultProfile()
        self.scheme_handler = LocalFileSchemeHandler(self)
        profile.installUrlSchemeHandler(b"local", self.scheme_handler)
        logger.info("Custom 'local://' scheme handler registered.")

    def _setup_bridge(self) -> None:
        """Initialize QWebChannel and register the JS bridge object."""
        self.js_bridge = JsBridge(self)
        self.channel = QWebChannel(self.web_view.page())
        self.web_view.page().setWebChannel(self.channel)
        self.channel.registerObject("pyBridge", self.js_bridge)

        # Connect bridge signals
        self.js_bridge.text_selected.connect(self.text_selected.emit)
        self.js_bridge.annotation_request.connect(self._handle_annotation_request)
        self.js_bridge.context_action.connect(self._handle_context_action)
        self.js_bridge.viewer_ready.connect(self._on_viewer_ready)
        self.js_bridge.page_changed.connect(
            lambda p: self.page_label.setText(f"Page: {p}")
        )

        logger.info("QWebChannel bridge initialized.")

    def load_pdf(self, file_path: str, paper_id: int) -> None:
        """Load a PDF file into the PDF.js viewer."""
        self.current_paper_id = paper_id
        self.current_pdf_path = os.path.abspath(file_path)
        self._viewer_ready = False

        # Build the URL for our custom bridge HTML
        bridge_html = RESOURCES_DIR / "viewer_bridge.html"
        if not bridge_html.exists():
            logger.error(f"viewer_bridge.html not found at {bridge_html}")
            return

        # Use custom local:// scheme for BOTH viewer and PDF
        # so they share the same origin and pass PDF.js security checks
        pdf_path_normalized = self.current_pdf_path.replace("\\", "/")
        pdf_url = f"local:///{pdf_path_normalized}"
        
        bridge_path_normalized = str(bridge_html).replace("\\", "/")
        viewer_url_str = f"local:///{bridge_path_normalized}?file={pdf_url}"

        logger.info(f"Loading PDF: {self.current_pdf_path}")
        logger.info(f"PDF URL: {pdf_url}")
        logger.info(f"Viewer URL: {viewer_url_str}")
        self.web_view.setUrl(QUrl(viewer_url_str))

    def _on_viewer_ready(self) -> None:
        """Called when PDF.js viewer signals it's fully loaded."""
        # Guard against multiple ready signals
        if self._viewer_ready:
            logger.debug("Viewer ready signal received again (ignoring)")
            return
            
        self._viewer_ready = True
        logger.info("PDF.js viewer ready, loading annotations...")

        # Load existing annotations for this paper
        if self.current_paper_id is not None:
            self._push_annotations_to_js()

    def _push_annotations_to_js(self) -> None:
        """Send saved annotations from DB to JavaScript for rendering."""
        if not self._viewer_ready or self.current_paper_id is None:
            return

        annotations = self.db.get_annotations(self.current_paper_id)
        if not annotations:
            return

        ann_data = []
        for a in annotations:
            ann_data.append({
                "id": a.id,
                "page": a.page,
                "content": a.content,
                "comment": a.comment,
                "color": a.color,
                "rects": json.loads(a.rects_json),
            })

        js_code = f"window.loadAnnotations({json.dumps(ann_data)});"
        self._run_js(js_code)
        logger.info(f"Pushed {len(ann_data)} annotations to JS.")

    def _handle_annotation_request(self, data_json: str) -> None:
        """Save an annotation from JavaScript to the database."""
        if self.current_paper_id is None:
            return

        try:
            data = json.loads(data_json)
            ann_id = self.db.add_annotation(
                paper_id=self.current_paper_id,
                page=data.get("page", 0),
                content=data.get("text", ""),
                comment=data.get("comment", ""),
                color=data.get("color", "#FFFF00"),
                rects_json=json.dumps(data.get("rects", [])),
            )
            # Notify JS with the new annotation ID
            self._run_js(f"window.confirmAnnotation({ann_id});")
            self.annotation_saved.emit(ann_id)
            logger.info(f"Annotation saved: id={ann_id}")
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Failed to save annotation: {e}")

    def _handle_context_action(self, action: str, text: str) -> None:
        """Handle contextual actions from the PDF viewer."""
        main_win = self.window()
        if hasattr(main_win, "open_ai_with_context"):
            main_win.open_ai_with_context(text, action)
        else:
            logger.warning(f"Context action '{action}' not handled - main window missing method.")

    def _refresh_pdf(self) -> None:
        """Reload the current PDF in the viewer."""
        if self.current_pdf_path:
            self.web_view.reload()

    def _run_js(self, code: str) -> None:
        """Execute JavaScript code in the web view."""
        self.web_view.page().runJavaScript(code)

    def cleanup(self) -> None:
        """Release resources."""
        self.web_view.setUrl(QUrl("about:blank"))
