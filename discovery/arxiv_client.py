"""
PaperMiner - ArXiv API Client
Search and retrieve papers from the ArXiv open-access repository.
Uses the ArXiv API (https://info.arxiv.org/help/api/index.html).
"""

import logging
import xml.etree.ElementTree as ET
from typing import List, Dict, Optional
from urllib.parse import quote

import httpx

logger = logging.getLogger(__name__)

ARXIV_API_BASE = "http://export.arxiv.org/api/query"


def search_arxiv(
    keyword: str,
    max_results: int = 10,
    sort_by: str = "relevance",
    start: int = 0,
) -> List[Dict[str, str]]:
    """
    Search ArXiv for papers matching the keyword.

    Args:
        keyword: Search query string
        max_results: Maximum number of results
        sort_by: 'relevance' or 'lastUpdatedDate' or 'submittedDate'
        start: Offset for pagination

    Returns:
        List of paper dicts with keys: title, authors, abstract, date, url, pdf_url, source
    """
    sort_map = {
        "relevance": "relevance",
        "Date (Newest)": "lastUpdatedDate",
        "Date (Oldest)": "submittedDate",
    }
    sort_param = sort_map.get(sort_by, "relevance")
    order = "descending" if sort_param != "submittedDate" else "ascending"

    params = {
        "search_query": f"all:{quote(keyword)}",
        "start": start,
        "max_results": max_results,
        "sortBy": sort_param,
        "sortOrder": order,
    }

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.get(ARXIV_API_BASE, params=params)
            response.raise_for_status()

        return _parse_arxiv_response(response.text)
    except httpx.TimeoutException:
        logger.error("ArXiv API request timed out.")
        return []
    except Exception as e:
        logger.error(f"ArXiv search error: {e}")
        return []


def _parse_arxiv_response(xml_text: str) -> List[Dict[str, str]]:
    """Parse ArXiv Atom XML response into a list of paper dicts."""
    ns = {
        "atom": "http://www.w3.org/2005/Atom",
        "arxiv": "http://arxiv.org/schemas/atom",
    }

    results = []
    try:
        root = ET.fromstring(xml_text)
        for entry in root.findall("atom:entry", ns):
            title_el = entry.find("atom:title", ns)
            summary_el = entry.find("atom:summary", ns)
            published_el = entry.find("atom:published", ns)

            # Authors
            authors = []
            for author_el in entry.findall("atom:author", ns):
                name_el = author_el.find("atom:name", ns)
                if name_el is not None and name_el.text:
                    authors.append(name_el.text.strip())

            # Links
            abs_url = ""
            pdf_url = ""
            for link_el in entry.findall("atom:link", ns):
                if link_el.get("title") == "pdf":
                    pdf_url = link_el.get("href", "")
                elif link_el.get("type") == "text/html":
                    abs_url = link_el.get("href", "")

            if not abs_url:
                id_el = entry.find("atom:id", ns)
                abs_url = id_el.text.strip() if id_el is not None and id_el.text else ""

            results.append({
                "title": _clean_text(title_el.text if title_el is not None else ""),
                "authors": ", ".join(authors[:5]) + ("..." if len(authors) > 5 else ""),
                "abstract": _clean_text(summary_el.text if summary_el is not None else ""),
                "date": (published_el.text[:10] if published_el is not None and published_el.text else ""),
                "url": abs_url,
                "pdf_url": pdf_url,
                "source": "ArXiv",
            })
    except ET.ParseError as e:
        logger.error(f"Failed to parse ArXiv XML: {e}")

    return results


def _clean_text(text: str) -> str:
    """Clean up whitespace in text extracted from XML."""
    if not text:
        return ""
    return " ".join(text.split())
