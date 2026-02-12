"""
PaperMiner - Abstract LLM Client
Provides a unified interface for LLM API calls.
Supports: DeepSeek, Zhipu/GLM, SiliconFlow, OpenAI-compatible endpoints.
"""

import json
import logging
import httpx
from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Generator, AsyncGenerator

from config import settings, LLMConfig

logger = logging.getLogger(__name__)


class LLMClient(ABC):
    """Abstract base class for LLM interactions."""

    @abstractmethod
    def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """Synchronous chat completion. Returns the assistant's response text."""
        ...

    @abstractmethod
    def chat_stream(self, messages: List[Dict[str, str]], **kwargs) -> Generator[str, None, None]:
        """Streaming chat completion. Yields response text chunks."""
        ...

    @abstractmethod
    def translate(self, text: str, target_lang: str = "zh-CN") -> str:
        """Translate text to target language, preserving academic context."""
        ...


class OpenAICompatibleClient(LLMClient):
    """
    Client for OpenAI-compatible API endpoints.
    Works with DeepSeek, Zhipu/GLM, SiliconFlow, and standard OpenAI.
    """

    def __init__(self, config: Optional[LLMConfig] = None) -> None:
        self.config = config or settings.llm
        self.base_url = self.config.base_url.rstrip("/")
        self.headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }
        self.timeout = httpx.Timeout(60.0, connect=10.0)
        logger.info(f"LLM client initialized: {self.config.provider} / {self.config.model_name}")

    def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """Send a chat completion request and return the full response."""
        payload = {
            "model": self.config.model_name,
            "messages": messages,
            "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
            "temperature": kwargs.get("temperature", self.config.temperature),
            "stream": False,
        }

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    f"{self.base_url}/chat/completions",
                    headers=self.headers,
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"]
        except httpx.TimeoutException:
            logger.error("LLM API request timed out.")
            return "[Error] API request timed out. Please try again."
        except httpx.HTTPStatusError as e:
            logger.error(f"LLM API error: {e.response.status_code} - {e.response.text}")
            return f"[Error] API returned status {e.response.status_code}"
        except Exception as e:
            logger.error(f"LLM API unexpected error: {e}")
            return f"[Error] {str(e)}"

    def chat_stream(self, messages: List[Dict[str, str]], **kwargs) -> Generator[str, None, None]:
        """Send a streaming chat request, yielding text chunks."""
        payload = {
            "model": self.config.model_name,
            "messages": messages,
            "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
            "temperature": kwargs.get("temperature", self.config.temperature),
            "stream": True,
        }

        try:
            with httpx.Client(timeout=self.timeout) as client:
                with client.stream(
                    "POST",
                    f"{self.base_url}/chat/completions",
                    headers=self.headers,
                    json=payload,
                ) as response:
                    response.raise_for_status()
                    for line in response.iter_lines():
                        if not line or line.startswith(":"):
                            continue
                        if line.startswith("data: "):
                            data_str = line[6:]
                            if data_str.strip() == "[DONE]":
                                break
                            try:
                                data = json.loads(data_str)
                                delta = data["choices"][0].get("delta", {})
                                content = delta.get("content", "")
                                if content:
                                    yield content
                            except json.JSONDecodeError:
                                continue
        except Exception as e:
            logger.error(f"LLM streaming error: {e}")
            yield f"\n[Error] {str(e)}"

    def translate(self, text: str, target_lang: str = "zh-CN") -> str:
        """Translate text while preserving academic terminology."""
        lang_names = {"zh-CN": "Chinese (Simplified)", "en": "English"}
        target_name = lang_names.get(target_lang, target_lang)

        messages = [
            {
                "role": "system",
                "content": (
                    f"You are a professional academic translator. Translate the following text "
                    f"to {target_name}. Preserve technical terms, mathematical notation, and "
                    f"academic writing style. Keep proper nouns in their original form when appropriate."
                ),
            },
            {"role": "user", "content": text},
        ]
        return self.chat(messages, temperature=0.3)


def create_llm_client(config: Optional[LLMConfig] = None) -> LLMClient:
    """Factory function to create the appropriate LLM client."""
    cfg = config or settings.llm
    # All supported providers use OpenAI-compatible API format
    return OpenAICompatibleClient(cfg)


# --- Provider-Specific Presets ---

PROVIDER_PRESETS: Dict[str, Dict[str, str]] = {
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "model_name": "deepseek-chat",
    },
    "zhipu": {
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "model_name": "glm-4-flash",
    },
    "siliconflow": {
        "base_url": "https://api.siliconflow.cn/v1",
        "model_name": "Qwen/Qwen2.5-7B-Instruct",
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "model_name": "gpt-4o-mini",
    },
}
