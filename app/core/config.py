"""
Core configuration – typed settings with environment variable support.

All values can be overridden via environment variables (case-insensitive).
"""

from __future__ import annotations

import os
from functools import lru_cache


class Settings:
    """Centralised, typed application configuration."""

    # ── Ollama ──────────────────────────────────────────────────────────────
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_LLM_MODEL: str = os.getenv("OLLAMA_LLM_MODEL", "gemini-3-flash-preview")
    OLLAMA_EMBED_MODEL: str = os.getenv("OLLAMA_EMBED_MODEL", "bge-m3")
    OLLAMA_TIMEOUT: float = float(os.getenv("OLLAMA_TIMEOUT", "300"))

    # ── ChromaDB ─────────────────────────────────────────────────────────────
    CHROMA_PATH: str = os.getenv("CHROMA_PATH", "./data/chroma")
    CHROMA_COLLECTION: str = os.getenv("CHROMA_COLLECTION", "qa_repo_context")

    # ── Generated tests ───────────────────────────────────────────────────────
    GENERATED_TESTS_DIR: str = os.getenv("GENERATED_TESTS_DIR", "./generated_tests")
    REPORTS_DIR: str = os.getenv("REPORTS_DIR", "./data/reports")

    # ── API server ────────────────────────────────────────────────────────────
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("API_PORT", "8000"))
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"

    # ── Pipeline ─────────────────────────────────────────────────────────────
    RAG_TOP_K: int = int(os.getenv("RAG_TOP_K", "8"))
    HEAL_CONFIDENCE_THRESHOLD: float = float(
        os.getenv("HEAL_CONFIDENCE_THRESHOLD", "0.65")
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a singleton Settings instance."""
    return Settings()
