"""
PaperMiner - Recommendation Agent
An AI-powered agent that converts natural language queries into search requests,
aggregates results, and provides summarized recommendations.
"""

import logging
from typing import List, Dict

from ai.llm_client import create_llm_client, LLMClient
from discovery.arxiv_client import search_arxiv
from discovery.hf_client import search_hf_papers

logger = logging.getLogger(__name__)


class RecommendationAgent:
    """
    AI agent that:
    1. Interprets user's research interest in natural language
    2. Generates optimal search queries
    3. Aggregates results from multiple sources
    4. Summarizes and recommends relevant papers
    """

    def __init__(self) -> None:
        self.llm: LLMClient = create_llm_client()

    def recommend(self, user_query: str, max_results: int = 10) -> Dict:
        """
        Full recommendation pipeline:
        1. Extract search keywords from user query
        2. Search ArXiv + HuggingFace
        3. Summarize findings

        Returns:
            Dict with keys: 'keywords', 'papers', 'summary'
        """
        # Step 1: Extract search keywords
        keywords = self._extract_keywords(user_query)
        logger.info(f"Agent extracted keywords: {keywords}")

        # Step 2: Search both sources
        all_papers: List[Dict[str, str]] = []
        for kw in keywords:
            arxiv_results = search_arxiv(kw, max_results=max_results // 2)
            all_papers.extend(arxiv_results)

            hf_results = search_hf_papers(kw, max_results=max_results // 2)
            all_papers.extend(hf_results)

        # Deduplicate by title similarity
        seen_titles = set()
        unique_papers = []
        for p in all_papers:
            title_key = p["title"].lower().strip()[:60]
            if title_key not in seen_titles:
                seen_titles.add(title_key)
                unique_papers.append(p)

        unique_papers = unique_papers[:max_results]

        # Step 3: Generate summary
        summary = self._summarize_results(user_query, unique_papers)

        return {
            "keywords": keywords,
            "papers": unique_papers,
            "summary": summary,
        }

    def _extract_keywords(self, query: str) -> List[str]:
        """Use LLM to extract optimal search keywords from a natural language query."""
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a search query optimizer for academic paper discovery. "
                    "Given a user's research interest, extract 1-3 concise search keywords "
                    "that would work well on ArXiv. Return ONLY a JSON array of strings. "
                    "Example: [\"transformer efficiency\", \"attention mechanism optimization\"]"
                ),
            },
            {"role": "user", "content": query},
        ]

        try:
            response = self.llm.chat(messages, temperature=0.3, max_tokens=200)
            import json
            # Try to parse JSON array from response
            response = response.strip()
            if response.startswith("["):
                keywords = json.loads(response)
                if isinstance(keywords, list) and all(isinstance(k, str) for k in keywords):
                    return keywords[:3]
        except Exception as e:
            logger.warning(f"Failed to parse keywords from LLM: {e}")

        # Fallback: use the original query as keyword
        return [query]

    def _summarize_results(self, query: str, papers: List[Dict[str, str]]) -> str:
        """Generate a summary of the search results."""
        if not papers:
            return "No papers found matching your query. Try refining your search terms."

        paper_list = ""
        for i, p in enumerate(papers[:10], 1):
            paper_list += f"{i}. **{p['title']}** ({p['date']}) - {p['authors']}\n"
            abstract_preview = p['abstract'][:200] + "..." if len(p['abstract']) > 200 else p['abstract']
            paper_list += f"   {abstract_preview}\n\n"

        messages = [
            {
                "role": "system",
                "content": (
                    "You are an academic research advisor. Based on the search results below, "
                    "provide a brief (3-5 sentences) summary of the research landscape and "
                    "highlight the 2-3 most promising/relevant papers for the user's query. "
                    "Be concise and actionable."
                ),
            },
            {
                "role": "user",
                "content": f"My research interest: {query}\n\nSearch results:\n{paper_list}",
            },
        ]

        try:
            return self.llm.chat(messages, temperature=0.5, max_tokens=500)
        except Exception as e:
            logger.error(f"Agent summary generation failed: {e}")
            return f"Found {len(papers)} papers. (Summary generation failed: {e})"
