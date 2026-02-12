/**
 * PaperMiner - PDF.js ↔ Python QWebChannel Bridge
 *
 * Responsibilities:
 * 1. Initialize QWebChannel and get reference to Python's pyBridge object
 * 2. Load PDF.js viewer in the iframe with the target PDF file
 * 3. Monitor text selection and show floating context menu
 * 4. Manage annotation highlights (create, render, persist)
 * 5. Forward all relevant events to Python via pyBridge
 */

// === Global State ===
let pyBridge = null;           // Python bridge object from QWebChannel
let selectedText = "";         // Currently selected text in the PDF
let selectionRects = [];       // Bounding rects of the selection
let selectionPage = 0;         // Page number of the selection
let annotations = [];          // Loaded annotations from DB
let viewerApp = null;          // Reference to PDFViewerApplication in the iframe

// === Initialization ===

/**
 * Initialize QWebChannel connection to Python.
 * Waits for both QWebChannel and qt.webChannelTransport to be available.
 */
function initBridge() {
    if (typeof QWebChannel === "undefined") {
        console.warn("QWebChannel not available, running in standalone mode.");
        initViewer();
        return;
    }

    // Wait for qt object to be injected by Qt
    if (typeof qt === "undefined" || !qt.webChannelTransport) {
        console.log("Waiting for qt.webChannelTransport...");
        setTimeout(initBridge, 50);
        return;
    }

    new QWebChannel(qt.webChannelTransport, function(channel) {
        pyBridge = channel.objects.pyBridge;
        console.log("QWebChannel bridge established.");
        initViewer();
    });
}

/**
 * Parse the PDF file URL from query parameters and load PDF.js viewer.
 */
function initViewer() {
    const params = new URLSearchParams(window.location.search);
    const fileUrl = params.get("file");

    if (!fileUrl) {
        console.error("No 'file' parameter provided in URL.");
        showToast("Error: No PDF file specified", 3000);
        return;
    }

    console.log("=== PDF.js Initialization ===");
    console.log("File URL from parameter:", fileUrl);
    console.log("Current location:", window.location.href);
    console.log("Raw URL params:", window.location.search);

    // Construct the PDF.js viewer URL with the file parameter
    // PDF.js viewer is located relative to our resources/ folder
    const pdfjsViewerPath = resolvePdfjsPath();
    console.log("PDF.js viewer path:", pdfjsViewerPath);
    
    const viewerUrl = pdfjsViewerPath + "?file=" + encodeURIComponent(fileUrl);
    console.log("Final viewer URL:", viewerUrl);

    const iframe = document.getElementById("viewer-frame");
    iframe.src = viewerUrl;

    // Wait for the iframe to load, then set up event listeners
    iframe.onload = function() {
        console.log("[OK] PDF.js iframe loaded successfully");
        setupIframeListeners(iframe);
    };
    
    // Log errors if iframe fails to load
    iframe.onerror = function(err) {
        console.error("[ERROR] Failed to load PDF.js viewer iframe:", err);
        showToast("Error: Failed to load PDF viewer", 5000);
    };
}

/**
 * Resolve the path to pdfjs-5.4.624-dist/web/viewer.html relative to this file.
 */
function resolvePdfjsPath() {
    // Strip query string first — it contains file paths with slashes
    // that would corrupt lastIndexOf("/") computation
    const href = window.location.href.split("?")[0];
    const basePath = href.substring(0, href.lastIndexOf("/"));
    return basePath + "/../pdfjs-5.4.624-dist/web/viewer.html";
}

// === Iframe Event Listeners ===

/**
 * Set up mouse/keyboard listeners on the PDF.js iframe for text selection detection.
 */
function setupIframeListeners(iframe) {
    try {
        const iframeDoc = iframe.contentDocument || iframe.contentWindow.document;
        const iframeWin = iframe.contentWindow;

        console.log("Setting up iframe listeners...");
        console.log("iframeDoc:", iframeDoc ? "OK" : "FAILED");
        console.log("iframeWin:", iframeWin ? "OK" : "FAILED");

        // Get reference to PDFViewerApplication (may not be ready immediately)
        viewerApp = iframeWin.PDFViewerApplication;

        if (!viewerApp || !viewerApp.eventBus) {
            // PDF.js not yet initialized, retry in a moment
            console.log("PDFViewerApplication not ready, retrying in 100ms...");
            setTimeout(function() {
                setupIframeListeners(iframe);
            }, 100);
            return;
        }

        console.log("[OK] PDFViewerApplication ready");

        // Listen for mouseup to detect text selection
        iframeDoc.addEventListener("mouseup", function(e) {
            setTimeout(function() {
                handleTextSelection(iframeWin, iframeDoc, e);
            }, 50); // Small delay to let selection finalize
        });

        // Hide context menu on click elsewhere
        iframeDoc.addEventListener("mousedown", function(e) {
            hideContextMenu();
        });

        // Track page changes
        if (viewerApp && viewerApp.eventBus) {
            viewerApp.eventBus.on("pagechanging", function(evt) {
                if (pyBridge) {
                    pyBridge.onPageChanged(evt.pageNumber);
                }
            });

            // Wait for PDF document to actually load before signaling ready
            viewerApp.eventBus.on("documentloaded", function() {
                console.log("[OK] PDF document fully loaded!");
                if (pyBridge) {
                    pyBridge.onViewerReady();
                }
            });
            
            // Listen for PDF loading errors
            viewerApp.eventBus.on("documenterror", function(evt) {
                console.error("[ERROR] PDF document error:", evt);
                showToast("Error loading PDF: " + (evt.message || "Unknown error"), 5000);
            });
        }

        console.log("[OK] Iframe listeners installed successfully");
    } catch (err) {
        console.error("[ERROR] Failed to set up iframe listeners:", err);
        console.error("Error details:", err.message, err.stack);
        showToast("Error: Failed to access PDF viewer (security restriction)", 5000);
    }
}

/**
 * Handle text selection in the PDF viewer iframe.
 */
function handleTextSelection(iframeWin, iframeDoc, mouseEvent) {
    const selection = iframeWin.getSelection();
    const text = selection ? selection.toString().trim() : "";

    if (text.length < 2) {
        hideContextMenu();
        selectedText = "";
        return;
    }

    selectedText = text;

    // Get selection bounding rects
    if (selection.rangeCount > 0) {
        const range = selection.getRangeAt(0);
        const rects = range.getClientRects();
        selectionRects = [];

        for (let i = 0; i < rects.length; i++) {
            selectionRects.push({
                x: rects[i].left,
                y: rects[i].top,
                w: rects[i].width,
                h: rects[i].height
            });
        }
    }

    // Determine the page number from the selection
    selectionPage = getPageFromSelection(iframeDoc, selection);

    // Notify Python of text selection
    if (pyBridge) {
        pyBridge.onTextSelected(text);
    }

    // Show floating context menu near the mouse position
    // Convert iframe coordinates to parent window coordinates
    const iframe = document.getElementById("viewer-frame");
    const iframeRect = iframe.getBoundingClientRect();
    const menuX = mouseEvent.clientX + iframeRect.left;
    const menuY = mouseEvent.clientY + iframeRect.top;

    showContextMenu(menuX, menuY);
}

/**
 * Determine which page the selection is on by checking parent elements.
 */
function getPageFromSelection(doc, selection) {
    if (!selection || selection.rangeCount === 0) return 0;

    let node = selection.anchorNode;
    while (node && node !== doc) {
        if (node.classList && node.classList.contains("page")) {
            const pageNum = parseInt(node.getAttribute("data-page-number"), 10);
            return isNaN(pageNum) ? 0 : pageNum;
        }
        node = node.parentNode;
    }
    return 0;
}

// === Context Menu ===

function showContextMenu(x, y) {
    const menu = document.getElementById("context-menu");
    menu.style.display = "block";

    // Clamp to viewport
    const menuRect = menu.getBoundingClientRect();
    if (x + menuRect.width > window.innerWidth) x = window.innerWidth - menuRect.width - 10;
    if (y + menuRect.height > window.innerHeight) y = window.innerHeight - menuRect.height - 10;

    menu.style.left = x + "px";
    menu.style.top = y + "px";
}

function hideContextMenu() {
    document.getElementById("context-menu").style.display = "none";
}

/**
 * Handle context menu button clicks.
 */
function contextAction(action) {
    hideContextMenu();

    if (!selectedText) return;

    if (action === "highlight") {
        createHighlight();
    } else if (pyBridge) {
        // Forward to Python for AI actions (explain, translate, save_to_notes)
        pyBridge.onContextAction(action, selectedText);
    }
}

// === Annotation / Highlight System ===

/**
 * Create a highlight annotation from the current selection.
 */
function createHighlight() {
    if (!selectedText || selectionRects.length === 0) return;

    const annotationData = {
        page: selectionPage,
        text: selectedText,
        rects: selectionRects,
        color: "#FFFF00",
        comment: ""
    };

    // Request Python to save the annotation
    if (pyBridge) {
        pyBridge.onAnnotationRequest(JSON.stringify(annotationData));
    }

    // Render the highlight immediately (optimistic)
    renderHighlight({
        id: -1,  // Temporary ID until Python confirms
        page: selectionPage,
        content: selectedText,
        rects: selectionRects,
        color: "#FFFF00",
        comment: ""
    });

    showToast("Highlight saved!");
}

/**
 * Load annotations from Python (called via pyBridge after viewer is ready).
 * @param {Array} annList - Array of annotation objects from the database.
 */
window.loadAnnotations = function(annList) {
    console.log("Loading " + annList.length + " annotations from DB.");
    annotations = annList;

    for (const ann of annList) {
        renderHighlight(ann);
    }
};

/**
 * Confirm an annotation was saved by Python and update its temporary ID.
 * @param {number} realId - The database ID of the saved annotation.
 */
window.confirmAnnotation = function(realId) {
    console.log("Annotation confirmed with ID:", realId);
    // Could update the DOM element's data attribute here if needed
};

/**
 * Render a highlight overlay on the PDF page.
 */
function renderHighlight(ann) {
    try {
        const iframe = document.getElementById("viewer-frame");
        const iframeDoc = iframe.contentDocument || iframe.contentWindow.document;

        // Find the page div
        const pageDiv = iframeDoc.querySelector('.page[data-page-number="' + ann.page + '"]');
        if (!pageDiv) {
            console.warn("Page div not found for page " + ann.page);
            return;
        }

        // Get the text layer container within the page
        const textLayer = pageDiv.querySelector(".textLayer");
        if (!textLayer) {
            console.warn("Text layer not found for page " + ann.page);
            return;
        }

        // Get scaling factor (PDF.js applies transforms)
        const pageRect = pageDiv.getBoundingClientRect();
        const textLayerRect = textLayer.getBoundingClientRect();

        for (const rect of ann.rects) {
            const highlight = iframeDoc.createElement("div");
            highlight.className = "pm-highlight";
            highlight.setAttribute("data-annotation-id", ann.id);
            highlight.style.cssText = `
                position: absolute;
                left: ${rect.x - textLayerRect.left + textLayer.scrollLeft}px;
                top: ${rect.y - textLayerRect.top + textLayer.scrollTop}px;
                width: ${rect.w}px;
                height: ${rect.h}px;
                background: ${ann.color}40;
                border-radius: 2px;
                pointer-events: auto;
                cursor: pointer;
                z-index: 10;
            `;

            highlight.title = ann.comment || ann.content || "";

            // Click to show annotation details
            highlight.addEventListener("click", function() {
                if (pyBridge) {
                    pyBridge.onContextAction("show_annotation", JSON.stringify({
                        id: ann.id,
                        content: ann.content,
                        comment: ann.comment
                    }));
                }
            });

            textLayer.appendChild(highlight);
        }
    } catch (err) {
        console.error("Error rendering highlight:", err);
    }
}

// === Utility ===

function showToast(message, duration) {
    duration = duration || 2000;
    const toast = document.getElementById("toast");
    toast.textContent = message;
    toast.style.display = "block";
    setTimeout(function() {
        toast.style.display = "none";
    }, duration);
}

// Hide context menu when clicking on the main document
document.addEventListener("mousedown", function() {
    hideContextMenu();
});

// Prevent context menu from closing immediately
document.getElementById("context-menu").addEventListener("mousedown", function(e) {
    e.stopPropagation();
});

// === Boot ===
document.addEventListener("DOMContentLoaded", initBridge);
