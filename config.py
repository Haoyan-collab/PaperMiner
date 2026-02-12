"""
PaperMiner - Global Configuration Module
Manages API keys, model selections, paths, and application settings.
"""

import json
import os
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional


# --- Path Constants ---
APP_ROOT = Path(__file__).parent.resolve()
LIBRARY_DIR = APP_ROOT / "paper_library"
DB_PATH = APP_ROOT / "library.db"
PDFJS_DIR = APP_ROOT / "pdfjs-5.4.624-dist"
PDFJS_VIEWER_URL = PDFJS_DIR / "web" / "viewer.html"
RESOURCES_DIR = APP_ROOT / "resources"
CONFIG_FILE = APP_ROOT / "settings.json"

# HuggingFace mirror for China mainland
HF_MIRROR_URL = "https://hf-mirror.com"

# Ensure directories exist
LIBRARY_DIR.mkdir(exist_ok=True)
RESOURCES_DIR.mkdir(exist_ok=True)


@dataclass
class LLMConfig:
    """Configuration for a single LLM provider."""
    provider: str = "deepseek"          # deepseek | zhipu | siliconflow | openai
    api_key: str = ""
    base_url: str = "https://api.deepseek.com/v1"
    model_name: str = "deepseek-chat"
    max_tokens: int = 4096
    temperature: float = 0.7


@dataclass
class EmbeddingConfig:
    """Configuration for embedding model (local or API)."""
    use_local: bool = True
    local_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    api_provider: str = "siliconflow"   # fallback to API if local fails
    api_key: str = ""
    api_base_url: str = "https://api.siliconflow.cn/v1"


@dataclass
class AppSettings:
    """Top-level application settings, serializable to JSON."""
    llm: LLMConfig = field(default_factory=LLMConfig)
    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)
    theme: str = "dark"                 # dark | light
    language: str = "zh"                # zh | en
    chunk_size: int = 512
    chunk_overlap: int = 64
    top_k_retrieval: int = 5

    def save(self, path: Optional[Path] = None) -> None:
        """Persist settings to a JSON file."""
        target = path or CONFIG_FILE
        with open(target, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, indent=2, ensure_ascii=False)

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "AppSettings":
        """Load settings from a JSON file, falling back to defaults."""
        target = path or CONFIG_FILE
        if not target.exists():
            settings = cls()
            settings.save(target)
            return settings
        try:
            with open(target, "r", encoding="utf-8") as f:
                data = json.load(f)
            return cls(
                llm=LLMConfig(**data.get("llm", {})),
                embedding=EmbeddingConfig(**data.get("embedding", {})),
                theme=data.get("theme", "dark"),
                language=data.get("language", "zh"),
                chunk_size=data.get("chunk_size", 512),
                chunk_overlap=data.get("chunk_overlap", 64),
                top_k_retrieval=data.get("top_k_retrieval", 5),
            )
        except (json.JSONDecodeError, TypeError):
            return cls()


# --- Singleton Settings Instance ---
settings = AppSettings.load()


def get_env_flags() -> dict:
    """Return Chromium/Qt environment flags for stable PDF rendering on Win11."""
    return {
        "QTWEBENGINE_CHROMIUM_FLAGS": "--disable-gpu --allow-file-access-from-files --no-sandbox",
        "QTWEBENGINE_DISABLE_SANDBOX": "1",
    }
