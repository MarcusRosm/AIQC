"""
Step 2b – ChromaDB Vector Store wrapper.

Provides a clean interface over the raw chromadb client:
  - upsert documents with embeddings
  - query by embedding vector
  - collection management
"""

from __future__ import annotations

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.core.config import get_settings
from app.core.exceptions import VectorStoreError
from app.core.logging import get_logger

logger = get_logger(__name__)


class ChromaStore:
    """
    Persistent ChromaDB collection wrapper.

    Lazily initialises the ChromaDB client on first access.
    All write operations are synchronous (ChromaDB is not async-native).
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._path = settings.CHROMA_PATH
        self._collection_name = settings.CHROMA_COLLECTION
        self._client: chromadb.ClientAPI | None = None
        self._collection: chromadb.Collection | None = None

    @property
    def client(self) -> chromadb.ClientAPI:
        if self._client is None:
            try:
                self._client = chromadb.PersistentClient(
                    path=self._path,
                    settings=ChromaSettings(anonymized_telemetry=False),
                )
                logger.info("ChromaDB initialised at '%s'", self._path)
            except Exception as exc:
                raise VectorStoreError(
                    f"Failed to initialise ChromaDB at {self._path!r}: {exc}"
                ) from exc
        return self._client

    @property
    def collection(self) -> chromadb.Collection:
        if self._collection is None:
            self._collection = self.client.get_or_create_collection(
                name=self._collection_name,
                metadata={"hnsw:space": "cosine"},
            )
            logger.info("Using collection '%s'", self._collection_name)
        return self._collection

    def upsert(
        self,
        docs: list[str],
        ids: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict] | None = None,
    ) -> None:
        """
        Upsert documents into the collection.

        Args:
            docs: Raw text documents.
            ids: Unique IDs (should be stable and file-path-based).
            embeddings: Float vectors (must match ``docs`` length).
            metadatas: Optional per-document metadata dicts.
        """
        if len(docs) != len(ids) != len(embeddings):
            raise VectorStoreError("docs, ids, and embeddings must have the same length.")
        try:
            self.collection.upsert(
                documents=docs,
                ids=ids,
                embeddings=embeddings,
                metadatas=metadatas or [{} for _ in docs],
            )
            logger.debug("Upserted %d documents into '%s'", len(docs), self._collection_name)
        except Exception as exc:
            raise VectorStoreError(f"ChromaDB upsert failed: {exc}") from exc

    def query(
        self,
        embedding: list[float],
        n_results: int = 8,
        where: dict | None = None,
    ) -> list[str]:
        """
        Query the collection for the ``n_results`` most similar documents.

        Args:
            embedding: The query vector.
            n_results: Maximum number of results to return.
            where: Optional metadata filter dict.

        Returns:
            List of matching document strings, ordered by similarity.
        """
        try:
            count = self.collection.count()
            if count == 0:
                logger.warning("Collection '%s' is empty – no context documents.", self._collection_name)
                return []
            actual_n = min(n_results, count)
            query_kwargs: dict = {
                "query_embeddings": [embedding],
                "n_results": actual_n,
                "include": ["documents"],
            }
            if where:
                query_kwargs["where"] = where

            results = self.collection.query(**query_kwargs)
            docs = results.get("documents", [[]])[0]
            logger.debug("Query returned %d document(s)", len(docs))
            return docs
        except Exception as exc:
            raise VectorStoreError(f"ChromaDB query failed: {exc}") from exc

    def count(self) -> int:
        """Return the number of documents in the collection."""
        return self.collection.count()

    def reset_collection(self) -> None:
        """Delete and recreate the collection (useful for re-indexing)."""
        try:
            self.client.delete_collection(self._collection_name)
            self._collection = None
            logger.warning("Collection '%s' reset.", self._collection_name)
        except Exception as exc:
            raise VectorStoreError(f"Failed to reset collection: {exc}") from exc
