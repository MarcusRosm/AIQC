"""
Step 2a – Embeddings via Ollama BGE-M3.

Wraps the Ollama async embed API to produce float vectors from text chunks.
"""

from __future__ import annotations

import ollama

from app.core.config import get_settings
from app.core.exceptions import VectorStoreError
from app.core.logging import get_logger

logger = get_logger(__name__)


class OllamaEmbedder:
    """
    Produces text embeddings using the Ollama ``/api/embed`` endpoint.

    Uses ``AsyncClient`` exclusively to stay non-blocking on the event loop.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._client = ollama.AsyncClient(host=settings.OLLAMA_BASE_URL)
        self._model = settings.OLLAMA_EMBED_MODEL

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """
        Embed a list of text strings.

        Args:
            texts: The texts to embed.

        Returns:
            A list of float vectors, one per input text.

        Raises:
            :exc:`VectorStoreError`: On Ollama API failure.
        """
        if not texts:
            return []

        logger.debug("Embedding %d text(s) with model '%s'", len(texts), self._model)
        try:
            vectors: list[list[float]] = []
            for text in texts:
                response = await self._client.embed(model=self._model, input=text)
                # ollama response: {"embeddings": [[...]]}
                embeddings = response.get("embeddings") or response.get("embedding")
                if not embeddings:
                    raise VectorStoreError(
                        f"Empty embedding returned for text: {text[:60]!r}"
                    )
                # Single text → single embedding list
                vec = embeddings[0] if isinstance(embeddings[0], list) else embeddings
                vectors.append(vec)
            return vectors
        except VectorStoreError:
            raise
        except Exception as exc:
            raise VectorStoreError(
                f"Ollama embed call failed: {exc}", detail=str(exc)
            ) from exc

    async def embed_one(self, text: str) -> list[float]:
        """Convenience method to embed a single string."""
        results = await self.embed([text])
        return results[0]
