"""
Step 2c – Repository Indexer.

Walks the repository file tree, chunks source files, embeds them via
OllamaEmbedder, and upserts into ChromaDB for later retrieval.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from app.core.logging import get_logger
from app.rag.embeddings import OllamaEmbedder
from app.rag.vector_store import ChromaStore

logger = get_logger(__name__)

# File extensions to index
_DEFAULT_EXTENSIONS: frozenset[str] = frozenset(
    {".py", ".ts", ".tsx", ".js", ".jsx", ".md", ".json"}
)
# Ignore common noisy directories
_IGNORE_DIRS: frozenset[str] = frozenset(
    {"node_modules", ".git", ".venv", "__pycache__", "dist", "build", ".next"}
)

_CHUNK_MAX_CHARS = 1024
_CHUNK_OVERLAP_CHARS = 160


class RepoIndexer:
    """
    Indexes a repository's source files into ChromaDB.

    Each file is chunked into overlapping text windows to preserve context.
    Chunk IDs are deterministic (path + chunk index) so re-indexing is safe.
    """

    def __init__(
        self,
        embedder: OllamaEmbedder | None = None,
        store: ChromaStore | None = None,
    ) -> None:
        self._embedder = embedder or OllamaEmbedder()
        self._store = store or ChromaStore()

    async def index_repo(
        self,
        root_dir: str,
        extensions: list[str] | None = None,
        reset: bool = False,
    ) -> int:
        """
        Walk ``root_dir`` and index all matching source files.

        Args:
            root_dir: Absolute path to the repository root.
            extensions: File extensions to include (with dot, e.g. ``.py``).
            reset: If ``True``, clears the collection before indexing.

        Returns:
            Total number of chunks indexed.
        """
        root = Path(root_dir).resolve()
        exts = frozenset(extensions) if extensions else _DEFAULT_EXTENSIONS

        if reset:
            self._store.reset_collection()

        logger.info("Indexing repo at '%s' (exts: %s)", root, sorted(exts))

        total_chunks = 0
        batch_docs: list[str] = []
        batch_ids: list[str] = []
        batch_metas: list[dict] = []

        for path in root.rglob("*"):
            if any(part in _IGNORE_DIRS for part in path.parts):
                continue
            if not path.is_file() or path.suffix not in exts:
                continue

            chunks = self._chunk_file(path, root)
            for chunk_idx, chunk_text in enumerate(chunks):
                chunk_id = self._make_id(path, chunk_idx)
                meta = {
                    "file": str(path.relative_to(root)),
                    "ext": path.suffix,
                    "chunk": chunk_idx,
                }
                batch_docs.append(chunk_text)
                batch_ids.append(chunk_id)
                batch_metas.append(meta)

                # Upsert in small batches to keep memory reasonable
                if len(batch_docs) >= 20:
                    await self._flush(batch_docs, batch_ids, batch_metas)
                    total_chunks += len(batch_docs)
                    batch_docs, batch_ids, batch_metas = [], [], []

        # Flush remainder
        if batch_docs:
            await self._flush(batch_docs, batch_ids, batch_metas)
            total_chunks += len(batch_docs)

        logger.info("Repository indexed: %d total chunks", total_chunks)
        return total_chunks

    async def _flush(
        self,
        docs: list[str],
        ids: list[str],
        metas: list[dict],
    ) -> None:
        embeddings = await self._embedder.embed(docs)
        self._store.upsert(docs, ids, embeddings, metas)

    @staticmethod
    def _chunk_file(path: Path, root: Path) -> list[str]:
        """Read a file and split it into overlapping chunks."""
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError as exc:
            logger.warning("Could not read %s: %s", path.relative_to(root), exc)
            return []

        if not text.strip():
            return []

        chunks: list[str] = []
        start = 0
        while start < len(text):
            end = start + _CHUNK_MAX_CHARS
            chunk = text[start:end]
            chunks.append(chunk)
            if end >= len(text):
                break
            start = end - _CHUNK_OVERLAP_CHARS

        return chunks

    @staticmethod
    def _make_id(path: Path, chunk_idx: int) -> str:
        """Create a stable, deterministic chunk ID."""
        digest = hashlib.sha1(str(path).encode()).hexdigest()[:12]
        return f"{digest}_{chunk_idx}"
