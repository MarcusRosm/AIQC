"""
Step 2d – Context Retriever.

Embeds the diff summary and queries ChromaDB to surface the most
relevant codebase snippets for the LLM's prompt context.
"""

from __future__ import annotations

from app.core.logging import get_logger
from app.core.schemas import DiffResult
from app.rag.embeddings import OllamaEmbedder
from app.rag.vector_store import ChromaStore

logger = get_logger(__name__)


class ContextRetriever:
    """
    Retrieves top-k relevant code snippets from ChromaDB given a diff.

    Composes :class:`OllamaEmbedder` and :class:`ChromaStore` to perform
    semantic retrieval; returns plain text snippets ready for prompt injection.
    """

    def __init__(
        self,
        embedder: OllamaEmbedder | None = None,
        store: ChromaStore | None = None,
    ) -> None:
        self._embedder = embedder or OllamaEmbedder()
        self._store = store or ChromaStore()

    async def retrieve(self, diff: DiffResult, top_k: int = 8) -> list[str]:
        """
        Retrieve the ``top_k`` most contextually relevant code snippets.

        The query is built from the diff summary plus file names and
        touched functions/classes to maximise semantic precision.

        Args:
            diff: Parsed diff result from :class:`DiffAnalyzer`.
            top_k: Maximum number of context snippets to return.

        Returns:
            List of raw text snippets, ranked by cosine similarity.
        """
        query_parts: list[str] = [diff.summary]

        for fc in diff.files[:10]:
            query_parts.append(f"File: {fc.path}")
            if fc.functions_touched:
                query_parts.append("Functions: " + ", ".join(fc.functions_touched))
            if fc.classes_touched:
                query_parts.append("Classes: " + ", ".join(fc.classes_touched))

        if diff.affected_routes:
            query_parts.append("Routes: " + ", ".join(diff.affected_routes[:5]))

        query_text = "\n".join(query_parts)
        logger.debug("Retrieval query (%d chars):\n%s", len(query_text), query_text[:300])

        query_vec = await self._embedder.embed_one(query_text)
        snippets = self._store.query(query_vec, n_results=top_k)

        logger.info("Retrieved %d context snippet(s)", len(snippets))
        return snippets
