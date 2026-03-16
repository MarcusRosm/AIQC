"""
FastAPI Application Factory.

Creates and configures the FastAPI application with:
- CORS middleware
- Lifespan (startup/shutdown) for ChromaDB warm-up
- All API routers mounted
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import health, pipeline, reports
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup and shutdown lifecycle handler."""
    settings = get_settings()
    configure_logging(settings.LOG_LEVEL)
    logger.info(
        "AI-Driven QA Platform starting up (model=%s, embed=%s)",
        settings.OLLAMA_LLM_MODEL,
        settings.OLLAMA_EMBED_MODEL,
    )
    # Pre-warm ChromaDB to surface config errors early
    try:
        from app.rag.vector_store import ChromaStore
        store = ChromaStore()
        doc_count = store.count()
        logger.info("ChromaDB ready – %d document(s) indexed.", doc_count)
    except Exception as exc:
        logger.warning("ChromaDB pre-warm failed (non-fatal): %s", exc)

    yield

    logger.info("AI-Driven QA Platform shutting down.")


def create_app() -> FastAPI:
    """FastAPI application factory (used by uvicorn ``factory=True``)."""
    settings = get_settings()

    app = FastAPI(
        title="AI-Driven QA Platform",
        description=(
            "AI-powered QA platform with self-healing Playwright tests, "
            "RAG-based context retrieval, and local LLM test generation."
        ),
        version="0.1.0",
        lifespan=_lifespan,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )

    # ── CORS ─────────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.DEBUG else ["http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Routers ───────────────────────────────────────────────────────────────
    app.include_router(health.router)
    app.include_router(pipeline.router)
    app.include_router(reports.router)

    @app.get("/", include_in_schema=False)
    async def root() -> dict:
        return {"message": "AI-Driven QA Platform", "docs": "/api/docs"}

    return app
