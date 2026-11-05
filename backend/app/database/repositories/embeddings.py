"""Repository for managing vector embedding tracking metadata."""

from datetime import datetime, timezone
import sqlite3
from typing import List, Optional, Tuple


class ChunkEmbeddingRepository:
    """Data access repository for chunk_embeddings table."""

    @staticmethod
    def record_embedding(
        conn: sqlite3.Connection,
        chunk_id: int,
        file_id: int,
        model_name: str,
        dimensions: int,
    ) -> None:
        """Insert or replace an embedding record for a chunk."""
        now_iso = datetime.now(timezone.utc).isoformat()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO chunk_embeddings (chunk_id, file_id, model_name, dimensions, embedded_at)
            VALUES (?, ?, ?, ?, ?);
            """,
            (chunk_id, file_id, model_name, dimensions, now_iso),
        )
        cursor.close()

    @staticmethod
    def record_batch(
        conn: sqlite3.Connection,
        records: List[Tuple[int, int, str, int]],
    ) -> int:
        """Insert or replace a batch of embedding records: (chunk_id, file_id, model_name, dimensions)."""
        if not records:
            return 0
        now_iso = datetime.now(timezone.utc).isoformat()
        rows = [
            (chunk_id, file_id, model_name, dimensions, now_iso)
            for chunk_id, file_id, model_name, dimensions in records
        ]
        cursor = conn.cursor()
        cursor.executemany(
            """
            INSERT OR REPLACE INTO chunk_embeddings (chunk_id, file_id, model_name, dimensions, embedded_at)
            VALUES (?, ?, ?, ?, ?);
            """,
            rows,
        )
        count = cursor.rowcount
        cursor.close()
        return count

    @staticmethod
    def get_unembedded_chunks(
        conn: sqlite3.Connection,
        limit: Optional[int] = None,
    ) -> List[sqlite3.Row]:
        """Fetch successfully indexed chunks that do not yet have vector embeddings."""
        cursor = conn.cursor()
        query = """
        SELECT c.id AS chunk_id, c.file_id, c.chunk_index, c.content,
               f.filename, f.metadata_json AS file_metadata, f.path AS file_path, f.file_type, f.folder_id,
               c.page_number, c.slide_number, c.sheet_name, c.row_number, c.start_line, c.end_line
        FROM chunks c
        JOIN files f ON c.file_id = f.id
        LEFT JOIN chunk_embeddings ce ON c.id = ce.chunk_id
        WHERE ce.chunk_id IS NULL AND f.status = 'success'
        ORDER BY c.file_id ASC, c.chunk_index ASC
        """
        if limit is not None:
            query += f" LIMIT {int(limit)}"
        cursor.execute(query)
        rows = cursor.fetchall()
        cursor.close()
        return rows

    @staticmethod
    def get_all_embedded_chunk_ids(conn: sqlite3.Connection) -> set[int]:
        """Return the set of all chunk IDs currently tracked as embedded in SQLite."""
        cursor = conn.cursor()
        cursor.execute("SELECT chunk_id FROM chunk_embeddings;")
        ids = {row[0] for row in cursor.fetchall()}
        cursor.close()
        return ids

    @staticmethod
    def delete_by_chunk_id(conn: sqlite3.Connection, chunk_id: int) -> int:
        """Delete embedding record for a chunk."""
        cursor = conn.cursor()
        cursor.execute("DELETE FROM chunk_embeddings WHERE chunk_id = ?;", (chunk_id,))
        count = cursor.rowcount
        cursor.close()
        return count

    @staticmethod
    def delete_by_file_id(conn: sqlite3.Connection, file_id: int) -> int:
        """Delete all embedding records for a file."""
        cursor = conn.cursor()
        cursor.execute("DELETE FROM chunk_embeddings WHERE file_id = ?;", (file_id,))
        count = cursor.rowcount
        cursor.close()
        return count

    @staticmethod
    def count_embedded(conn: sqlite3.Connection) -> int:
        """Count total embedded chunks."""
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM chunk_embeddings;")
        count = cursor.fetchone()[0]
        cursor.close()
        return count

    @staticmethod
    def count_unembedded(conn: sqlite3.Connection) -> int:
        """Count successfully indexed chunks that do not yet have embeddings."""
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM chunks c
            JOIN files f ON c.file_id = f.id
            LEFT JOIN chunk_embeddings ce ON c.id = ce.chunk_id
            WHERE ce.chunk_id IS NULL AND f.status = 'success';
            """
        )
        count = cursor.fetchone()[0]
        cursor.close()
        return count

