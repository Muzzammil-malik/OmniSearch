"""Persistent vector storage implementation using ChromaDB."""

import logging
from pathlib import Path
import threading
from typing import Any, Dict, List, Optional, Set, Tuple

from app.core.dependencies import ChromaDependencyManager, classify_native_error

logger = logging.getLogger(__name__)


class VectorStoreError(Exception):
    """Base exception for vector store operations."""


class VectorStoreUnavailableError(VectorStoreError):
    """Raised when ChromaDB vector store or its native dependencies cannot initialize."""

    def __init__(
        self,
        message: str,
        category: str = "unavailable",
        original_exception: Optional[Exception] = None,
    ) -> None:
        super().__init__(message)
        self.category = category
        self.original_exception = original_exception


def chunk_id_to_chroma_id(chunk_id: int) -> str:
    """Format canonical SQLite integer chunk ID to Chroma string ID."""
    return f"chunk_{chunk_id}"


def chroma_id_to_chunk_id(chroma_id: str) -> int:
    """Parse integer chunk ID from Chroma string ID."""
    if chroma_id.startswith("chunk_"):
        return int(chroma_id[6:])
    return int(chroma_id)


class ChromaVectorStore:
    """Vector database client wrapping ChromaDB PersistentClient."""

    def __init__(
        self,
        persist_dir: Path,
        collection_name: str = "omnisearch_chunks",
    ) -> None:
        self.persist_dir = Path(persist_dir)
        self.collection_name = collection_name
        self._client = None
        self._collection = None
        self._init_error: Optional[Exception] = None
        self._error_category: Optional[str] = None
        self._is_available: Optional[bool] = None
        self._op_lock = threading.RLock()

    def is_available(self) -> bool:
        """Check if vector store can be initialized and reached."""
        if self._is_available is not None:
            return self._is_available
        try:
            _ = self.client
            return True
        except Exception:
            return False

    def get_initialization_error(self) -> Optional[Exception]:
        return self._init_error

    def get_error_category(self) -> Optional[str]:
        return self._error_category

    @property
    def client(self):
        """Lazy-initialize ChromaDB client."""
        with self._op_lock:
            if self._is_available is False:
                raise VectorStoreUnavailableError(
                    f"ChromaDB vector store is unavailable ({self._error_category}): {self._init_error}",
                    category=self._error_category or "unavailable",
                    original_exception=self._init_error,
                ) from self._init_error

            if self._client is None:
                try:
                    chromadb = ChromaDependencyManager.get_instance().ensure_chromadb()
                    self.persist_dir.mkdir(parents=True, exist_ok=True)
                    self._client = chromadb.PersistentClient(path=str(self.persist_dir))
                    self._is_available = True
                except Exception as exc:
                    self._is_available = False
                    self._init_error = exc
                    self._error_category = classify_native_error(exc)
                    logger.error("Failed to initialize ChromaDB PersistentClient (%s): %s", self._error_category, exc)
                    raise VectorStoreUnavailableError(
                        f"ChromaDB vector store is unavailable ({self._error_category}): {exc}",
                        category=self._error_category,
                        original_exception=exc,
                    ) from exc
            return self._client

    @property
    def collection(self):
        """Lazy-initialize ChromaDB collection with cosine distance metric."""
        with self._op_lock:
            if self._collection is None:
                try:
                    self._collection = self.client.get_or_create_collection(
                        name=self.collection_name,
                        metadata={"hnsw:space": "cosine"},
                    )
                except Exception as exc:
                    self._is_available = False
                    self._init_error = exc
                    self._error_category = classify_native_error(exc)
                    raise VectorStoreUnavailableError(
                        f"ChromaDB collection access failed ({self._error_category}): {exc}",
                        category=self._error_category,
                        original_exception=exc,
                    ) from exc
            return self._collection

    def count(self) -> int:
        """Return total number of vectors stored in the collection.

        Raises:
            VectorStoreUnavailableError: If ChromaDB cannot be initialized or accessed.
        """
        try:
            return self.collection.count()
        except VectorStoreUnavailableError:
            raise
        except Exception as e:
            self._is_available = False
            self._init_error = e
            self._error_category = classify_native_error(e)
            logger.error("Failed to get vector count: %s", e)
            raise VectorStoreUnavailableError(
                f"Failed to get vector count ({self._error_category}): {e}",
                category=self._error_category,
                original_exception=e,
            ) from e

    def get_all_chunk_ids(self) -> Set[int]:
        """Return all integer chunk IDs currently present in the vector store.

        Raises:
            VectorStoreUnavailableError: If ChromaDB cannot be initialized or accessed.
        """
        try:
            total = self.count()
            if total == 0:
                return set()
            data = self.collection.get(include=[])
            return {chroma_id_to_chunk_id(cid) for cid in data.get("ids", [])}
        except VectorStoreUnavailableError:
            raise
        except Exception as e:
            self._is_available = False
            self._init_error = e
            self._error_category = classify_native_error(e)
            logger.error("Failed to retrieve chunk IDs from Chroma: %s", e)
            raise VectorStoreUnavailableError(
                f"Failed to retrieve chunk IDs ({self._error_category}): {e}",
                category=self._error_category,
                original_exception=e,
            ) from e

    def upsert(
        self,
        chunk_ids: List[int],
        embeddings: List[List[float]],
        metadatas: Optional[List[Dict[str, Any]]] = None,
        documents: Optional[List[str]] = None,
    ) -> None:
        """Upsert chunk embeddings and associated metadata into ChromaDB.

        Args:
            chunk_ids: List of integer chunk IDs from SQLite.
            embeddings: List of embedding vectors.
            metadatas: Optional list of metadata dicts (file_id, file_type, folder_id, etc.).
            documents: Optional raw document text contents.
        """
        if not chunk_ids:
            return

        if len(chunk_ids) != len(embeddings):
            raise ValueError(
                f"Chunk ID count ({len(chunk_ids)}) does not match embeddings count ({len(embeddings)})"
            )

        ids = [chunk_id_to_chroma_id(cid) for cid in chunk_ids]

        # Sanitize metadatas (Chroma only accepts primitive types: bool, int, float, str)
        sanitized_metadatas: Optional[List[Dict[str, Any]]] = None
        if metadatas:
            sanitized_metadatas = []
            for meta in metadatas:
                sanitized_meta = {}
                for k, v in meta.items():
                    if v is not None and isinstance(v, (str, int, float, bool)):
                        sanitized_meta[k] = v
                    elif v is not None:
                        sanitized_meta[k] = str(v)
                sanitized_metadatas.append(sanitized_meta)

        self.collection.upsert(
            ids=ids,
            embeddings=embeddings,
            metadatas=sanitized_metadatas,
            documents=documents,
        )

    def delete(self, chunk_ids: List[int]) -> None:
        """Delete specific chunks by their SQLite chunk IDs."""
        if not chunk_ids:
            return
        ids = [chunk_id_to_chroma_id(cid) for cid in chunk_ids]
        try:
            self.collection.delete(ids=ids)
        except Exception as e:
            logger.warning("Failed to delete chunks %s from Chroma: %s", chunk_ids, e)

    def delete_by_file_id(self, file_id: int) -> None:
        """Delete all chunk vectors belonging to a specific file ID."""
        try:
            self.collection.delete(where={"file_id": file_id})
        except Exception as e:
            logger.warning("Failed to delete vectors for file_id %d from Chroma: %s", file_id, e)

    def delete_by_folder_id(self, folder_id: int) -> None:
        """Delete all chunk vectors belonging to a specific folder ID."""
        try:
            self.collection.delete(where={"folder_id": folder_id})
        except Exception as e:
            logger.warning("Failed to delete vectors for folder_id %d from Chroma: %s", folder_id, e)

    def query(
        self,
        query_embedding: List[float],
        n_results: int = 20,
        where: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Query ChromaDB for nearest neighbor vectors using cosine distance.

        Args:
            query_embedding: L2-normalized query vector.
            n_results: Maximum number of results to retrieve.
            where: Optional ChromaDB metadata filter dictionary.

        Returns:
            List of result dicts containing:
            - chunk_id: int
            - distance: float (cosine distance)
            - similarity: float (1.0 - distance, clamped to [-1.0, 1.0])
            - metadata: dict
            - document: Optional[str]
        """
        total_vectors = self.count()
        if total_vectors == 0:
            return []

        limit = min(n_results, total_vectors)
        if limit <= 0:
            return []

        try:
            query_args: Dict[str, Any] = {
                "query_embeddings": [query_embedding],
                "n_results": limit,
            }
            if where:
                query_args["where"] = where

            raw_results = self.collection.query(**query_args)
        except Exception as e:
            logger.error("Vector similarity query failed in Chroma: %s", e)
            return []

        ids_list = raw_results.get("ids", [[]])[0]
        distances_list = raw_results.get("distances", [[]])[0]
        metadatas_list = raw_results.get("metadatas", [[]])[0] if raw_results.get("metadatas") else []
        documents_list = raw_results.get("documents", [[]])[0] if raw_results.get("documents") else []

        results: List[Dict[str, Any]] = []
        for i, cid_str in enumerate(ids_list):
            chunk_id = chroma_id_to_chunk_id(cid_str)
            distance = float(distances_list[i]) if i < len(distances_list) else 0.0
            # Cosine similarity = 1.0 - distance
            similarity = max(-1.0, min(1.0, 1.0 - distance))
            meta = metadatas_list[i] if i < len(metadatas_list) and metadatas_list[i] else {}
            doc = documents_list[i] if i < len(documents_list) else None

            results.append({
                "chunk_id": chunk_id,
                "distance": distance,
                "similarity": similarity,
                "metadata": meta,
                "document": doc,
            })

        return results

    def reset(self) -> None:
        """Reset or clear the entire collection."""
        try:
            self.client.delete_collection(name=self.collection_name)
            self._collection = None
        except Exception as e:
            logger.warning("Error deleting Chroma collection: %s", e)
            self._collection = None

