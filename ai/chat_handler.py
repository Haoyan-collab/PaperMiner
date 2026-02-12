"""
PaperMiner - Chat Handler
Orchestrates RAG-based chat flows:
  - "Chat with Paper": Answers using the currently open paper's chunks
  - "Chat with Library": Retrieves from all indexed papers
  - Contextual actions (explain, translate)
"""

import json
import logging
from typing import List, Dict, Optional

from config import settings
from core.database import DatabaseManager
from core.models import TextChunk, ChatMessage
from ai.llm_client import create_llm_client, LLMClient
from ai.rag_engine import EmbeddingEngine, search_similar_chunks

logger = logging.getLogger(__name__)


class ChatHandler:
    """
    Manages chat sessions with RAG context injection.
    Thread-safe: each handler should be used within a single QThread worker.
    """

    def __init__(self, db: DatabaseManager) -> None:
        self.db = db
        self.llm: LLMClient = create_llm_client()
        self.embed_engine = EmbeddingEngine()
        self.history: List[Dict[str, str]] = []

    def chat_with_paper(self, paper_id: int, user_message: str) -> str:
        """Answer a question using RAG on the currently open paper."""
        chunks = self.db.get_chunks(paper_id)
        if not chunks:
            return self._plain_chat(user_message, context_note="(This paper has not been indexed for RAG yet.)")

        return self._rag_chat(user_message, chunks)

    def chat_with_library(self, user_message: str) -> str:
        """Answer a question using RAG across the entire library."""
        chunks = self.db.get_all_chunks()
        if not chunks:
            return self._plain_chat(user_message, context_note="(No papers have been indexed in the library yet.)")

        return self._rag_chat(user_message, chunks)

    def explain_text(self, text: str) -> str:
        """Generate an academic explanation for selected text."""
        messages = [
            {
                "role": "system",
                "content": (
                    "You are an expert academic research assistant. "
                    "Explain the following text clearly and concisely. "
                    "If it contains technical terms, formulas, or jargon, break them down. "
                    "Respond in the same language as the input text."
                ),
            },
            {"role": "user", "content": f"Please explain this:\n\n{text}"},
        ]
        return self.llm.chat(messages, temperature=0.5)

    def translate_text(self, text: str, target_lang: str = "zh-CN") -> str:
        """Translate selected text preserving academic context."""
        return self.llm.translate(text, target_lang)

    def free_chat(self, user_message: str) -> str:
        """Plain chat without RAG context."""
        return self._plain_chat(user_message)

    # ---- Internal Methods ----

    def _rag_chat(self, user_message: str, chunks: List[TextChunk]) -> str:
        """Perform RAG: embed query → retrieve → generate answer."""
        # Generate query embedding
        query_emb = self.embed_engine.embed_texts([user_message])
        if not query_emb or not query_emb[0]:
            return self._plain_chat(user_message, context_note="(Embedding generation failed, answering without context.)")

        # Retrieve relevant chunks
        top_k = settings.top_k_retrieval
        relevant = search_similar_chunks(query_emb[0], chunks, top_k=top_k)

        if not relevant:
            return self._plain_chat(user_message, context_note="(No relevant passages found in the paper(s).)")

        # Build context from retrieved chunks
        context_parts = []
        for i, (chunk, score) in enumerate(relevant, 1):
            context_parts.append(
                f"[Passage {i}] (Page {chunk.page_start}, Relevance: {score:.2f})\n{chunk.text}"
            )
        context_text = "\n\n".join(context_parts)

        # Build messages with context
        system_prompt = (
            "You are PaperMiner AI, an academic research assistant. "
            "Answer the user's question based on the following passages from their research papers. "
            "Cite passage numbers [Passage N] when referencing specific content. "
            "If the passages don't contain enough information to answer, say so honestly. "
            "Maintain academic rigor and precision."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"## Retrieved Context:\n\n{context_text}\n\n## Question:\n{user_message}"},
        ]

        # Include recent history for continuity
        if self.history:
            recent = self.history[-4:]  # Last 2 exchanges
            messages = [messages[0]] + recent + [messages[-1]]

        response = self.llm.chat(messages)

        # Update history
        self.history.append({"role": "user", "content": user_message})
        self.history.append({"role": "assistant", "content": response})

        return response

    def _plain_chat(self, user_message: str, context_note: str = "") -> str:
        """Fallback: chat without RAG context."""
        system_prompt = (
            "You are PaperMiner AI, an academic research assistant. "
            "Help the user with their research questions. "
            f"{context_note}"
        )

        messages = [{"role": "system", "content": system_prompt}]
        if self.history:
            messages.extend(self.history[-4:])
        messages.append({"role": "user", "content": user_message})

        response = self.llm.chat(messages)

        self.history.append({"role": "user", "content": user_message})
        self.history.append({"role": "assistant", "content": response})

        return response

    def clear_history(self) -> None:
        """Reset conversation history."""
        self.history.clear()
