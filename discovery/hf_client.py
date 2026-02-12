"""
PaperMiner - HuggingFace Daily Papers Client
Fetches trending/daily papers from HuggingFace using the mirror endpoint.
"""

import logging
from typing import List, Dict

import httpx

from config import HF_MIRROR_URL

logger = logging.getLogger(__name__)

# HuggingFace Daily Papers API endpoint (using mirror for China mainland)
HF_PAPERS_API = f"{HF_MIRROR_URL}/api/daily_papers"


def search_hf_papers(
    keyword: str = "",
    max_results: int = 10,
) -> List[Dict[str, str]]:
    """
    Fetch daily/trending papers from HuggingFace.

    Note: The HF daily papers API returns trending papers; keyword filtering
    is done client-side since the API doesn't support search queries directly.

    Args:
        keyword: Optional keyword to filter results client-side
        max_results: Maximum number of results to return

    Returns:
        List of paper dicts with keys: title, authors, abstract, date, url, pdf_url, source
    """
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.get(HF_PAPERS_API)
            response.raise_for_status()
            data = response.json()

        results = []
        for item in data:
            paper = item.get("paper", {})
            title = paper.get("title", "")
            summary = paper.get("summary", "")
            authors_list = paper.get("authors", [])
            published = paper.get("publishedAt", "")[:10]
            paper_id = paper.get("id", "")

            # Client-side keyword filtering
            if keyword:
                keyword_lower = keyword.lower()
                if (keyword_lower not in title.lower() and
                    keyword_lower not in summary.lower()):
                    continue

            author_names = []
            for a in authors_list[:5]:
                name = a.get("name", "") if isinstance(a, dict) else str(a)
                if name:
                    author_names.append(name)

            results.append({
                "title": title,
                "authors": ", ".join(author_names) + ("..." if len(authors_list) > 5 else ""),
                "abstract": summary,
                "date": published,
                "url": f"https://huggingface.co/papers/{paper_id}" if paper_id else "",
                "pdf_url": f"https://arxiv.org/pdf/{paper_id}" if paper_id else "",
                "source": "HuggingFace",
            })

            if len(results) >= max_results:
                break

        logger.info(f"HuggingFace papers fetched: {len(results)} results.")
        return results

    except httpx.TimeoutException:
        logger.error("HuggingFace API request timed out.")
        return []
    except Exception as e:
        logger.error(f"HuggingFace papers error: {e}")
        return []
