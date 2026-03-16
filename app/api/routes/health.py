"""
API Route: health

GET /api/health – readiness probe for the platform and its dependencies.
"""

from __future__ import annotations

import httpx

from fastapi import APIRouter

from app.core.config import get_settings
from app.core.logging import get_logger
from app.rag.vector_store import ChromaStore

logger = get_logger(__name__)
router = APIRouter(prefix="/api/health", tags=["health"])


@router.get("")
async def health_check() -> dict:
    """
    Returns the health status of the platform and its dependencies.

    - **ollama**: Whether the Ollama HTTP API is reachable
    - **chromadb**: Whether the ChromaDB collection initialises correctly
    """
    settings = get_settings()

    # Check Ollama
    ollama_ok = False
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{settings.OLLAMA_BASE_URL}/api/tags")
            ollama_ok = resp.status_code == 200
    except Exception as exc:
        logger.warning("Ollama health check failed: %s", exc)

    # Check ChromaDB
    chroma_ok = False
    try:
        store = ChromaStore()
        store.count()  # triggers lazy client init
        chroma_ok = True
    except Exception as exc:
        logger.warning("ChromaDB health check failed: %s", exc)

    status = "ok" if (ollama_ok and chroma_ok) else "degraded"
    return {
        "status": status,
        "ollama": ollama_ok,
        "chromadb": chroma_ok,
        "llm_model": settings.OLLAMA_LLM_MODEL,
        "embed_model": settings.OLLAMA_EMBED_MODEL,
    }
