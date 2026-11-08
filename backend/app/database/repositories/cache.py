"""Repository for content-addressed embedding caching and deduplication."""

from datetime import datetime, timezone
import hashlib
import sqlite3
import struct
from typing import Dict, List, Optional, Tuple
import numpy as np


class EmbeddingCacheRepository:
    """Data access repository for embedding_cache table."""

    PIPELINE_VERSION = 1

    @classmethod
    def compute_cache_key(
        cls,
        content_sha256: str,
        model_name: str,
        modality: str,
        dimensions: int,
        pipeline_version: int = PIPELINE_VERSION,
    ) -> str:
        """Compute a deterministic hash representing the exact semantic inputs."""
        identity = f"{content_sha256}:{model_name}:{modality}:{dimensions}:v{pipeline_version}"
        return hashlib.sha256(identity.encode("utf-8")).hexdigest()

    @staticmethod
    def vector_to_blob(vector: List[float]) -> bytes:
        """Serialize a float vector into binary BLOB."""
        return np.array(vector, dtype=np.float32).tobytes()

    @staticmethod
    def blob_to_vector(blob: bytes) -> List[float]:
        """Deserialize a binary BLOB into float list."""
        return np.frombuffer(blob, dtype=np.float32).tolist()

    @classmethod
    def get(cls, conn: sqlite3.Connection, cache_key: str) -> Optional[List[float]]:
        """Fetch a cached embedding vector by its deterministic cache key."""
        cursor = conn.cursor()
        cursor.execute("SELECT embedding_blob FROM embedding_cache WHERE cache_key = ?;", (cache_key,))
        row = cursor.fetchone()
        cursor.close()
        if not row:
            return None
        return cls.blob_to_vector(row[0])

    @classmethod
    def get_batch(cls, conn: sqlite3.Connection, cache_keys: List[str]) -> Dict[str, List[float]]:
        """Fetch multiple cached embedding vectors in a single SQLite query."""
        if not cache_keys:
            return {}

        results: Dict[str, List[float]] = {}
        # Chunk into batches of 500 for SQLite parameter limits
        chunk_size = 500
        cursor = conn.cursor()
        for i in range(0, len(cache_keys), chunk_size):
            batch = cache_keys[i : i + chunk_size]
            placeholders = ",".join("?" for _ in batch)
            cursor.execute(
                f"SELECT cache_key, embedding_blob FROM embedding_cache WHERE cache_key IN ({placeholders});",
                batch,
            )
            for row in cursor.fetchall():
                results[row[0]] = cls.blob_to_vector(row[1])
        cursor.close()
        return results

    @classmethod
    def put(
        cls,
        conn: sqlite3.Connection,
        cache_key: str,
        content_sha256: str,
        model_name: str,
        modality: str,
        dimensions: int,
        vector: List[float],
        pipeline_version: int = PIPELINE_VERSION,
    ) -> None:
        """Store an embedding vector in the cache."""
        now_iso = datetime.now(timezone.utc).isoformat()
        blob = cls.vector_to_blob(vector)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO embedding_cache
            (cache_key, content_sha256, model_name, modality, dimensions, pipeline_version, embedding_blob, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (cache_key, content_sha256, model_name, modality, dimensions, pipeline_version, blob, now_iso),
        )
        cursor.close()

    @classmethod
    def put_batch(
        cls,
        conn: sqlite3.Connection,
        records: List[Tuple[str, str, str, str, int, List[float]]],
        pipeline_version: int = PIPELINE_VERSION,
    ) -> int:
        """Insert or replace a batch of embedding records: (cache_key, content_sha256, model_name, modality, dimensions, vector)."""
        if not records:
            return 0
        now_iso = datetime.now(timezone.utc).isoformat()
        rows = [
            (k, h, m, mod, dim, pipeline_version, cls.vector_to_blob(vec), now_iso)
            for k, h, m, mod, dim, vec in records
        ]
        cursor = conn.cursor()
        cursor.executemany(
            """
            INSERT OR REPLACE INTO embedding_cache
            (cache_key, content_sha256, model_name, modality, dimensions, pipeline_version, embedding_blob, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """,
            rows,
        )
        count = cursor.rowcount
        cursor.close()
        return count

    @staticmethod
    def count(conn: sqlite3.Connection) -> int:
        """Return total number of cached vectors."""
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM embedding_cache;")
        cnt = cursor.fetchone()[0]
        cursor.close()
        return cnt

