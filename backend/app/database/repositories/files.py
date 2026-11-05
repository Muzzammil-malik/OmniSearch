"""Files repository for managing document metadata and indexing states."""

from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import List, Optional, Set
from app.schemas.processing import FileRecord


def normalize_file_path(path: str) -> str:
    """Normalize file path for consistent unique constraints."""
    return str(Path(path).resolve())


class FileRepository:
    """Data access repository for files table."""

    @staticmethod
    def upsert(conn: sqlite3.Connection, record: FileRecord) -> int:
        """Insert or update a file record matching the unique file path.

        Returns:
            The primary key integer ID of the inserted or updated file.
        """
        norm_path = normalize_file_path(record.path)
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM files WHERE path = ?;", (norm_path,))
        existing = cursor.fetchone()

        now_iso = datetime.now(timezone.utc).isoformat()

        if existing:
            file_id = existing["id"]
            cursor.execute(
                """
                UPDATE files
                SET folder_id = ?,
                    filename = ?,
                    extension = ?,
                    file_type = ?,
                    sha256 = ?,
                    size_bytes = ?,
                    modified_at = ?,
                    indexed_at = ?,
                    status = ?,
                    error_message = ?,
                    metadata_json = ?
                WHERE id = ?;
                """,
                (
                    record.folder_id,
                    record.filename,
                    record.extension,
                    record.file_type,
                    record.sha256,
                    record.size_bytes,
                    record.modified_at,
                    now_iso,
                    record.status,
                    record.error_message,
                    record.metadata_json or "{}",
                    file_id,
                ),
            )
            cursor.close()
            return file_id

        cursor.execute(
            """
            INSERT INTO files (
                folder_id, path, filename, extension, file_type, sha256,
                size_bytes, modified_at, indexed_at, status, error_message, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                record.folder_id,
                norm_path,
                record.filename,
                record.extension,
                record.file_type,
                record.sha256,
                record.size_bytes,
                record.modified_at,
                now_iso,
                record.status,
                record.error_message,
                record.metadata_json or "{}",
            ),
        )
        file_id = cursor.lastrowid
        cursor.close()
        return file_id

    @classmethod
    def get_by_path(cls, conn: sqlite3.Connection, path: str) -> Optional[FileRecord]:
        """Fetch file record by normalized file path."""
        norm_path = normalize_file_path(path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM files WHERE path = ?;", (norm_path,))
        row = cursor.fetchone()
        cursor.close()
        return cls._row_to_record(row) if row else None

    @classmethod
    def get_by_id(cls, conn: sqlite3.Connection, file_id: int) -> Optional[FileRecord]:
        """Fetch file record by primary key."""
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM files WHERE id = ?;", (file_id,))
        row = cursor.fetchone()
        cursor.close()
        return cls._row_to_record(row) if row else None

    @classmethod
    def list_by_folder(cls, conn: sqlite3.Connection, folder_id: int) -> List[FileRecord]:
        """List all files tracked under a specific folder."""
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM files WHERE folder_id = ? ORDER BY path ASC;", (folder_id,))
        rows = cursor.fetchall()
        cursor.close()
        return [cls._row_to_record(r) for r in rows]

    @staticmethod
    def delete(conn: sqlite3.Connection, file_id: int) -> bool:
        """Delete a file record. Foreign key CASCADE removes all corresponding chunks."""
        cursor = conn.cursor()
        cursor.execute("DELETE FROM files WHERE id = ?;", (file_id,))
        deleted = cursor.rowcount > 0
        cursor.close()
        return deleted

    @staticmethod
    def delete_missing_in_folder(
        conn: sqlite3.Connection,
        folder_id: int,
        present_paths: Set[str],
    ) -> List[str]:
        """Remove file records for a folder that no longer exist on disk.

        Args:
            conn: Open connection in active transaction.
            folder_id: Folder identifier.
            present_paths: Set of normalized paths discovered during current scan.

        Returns:
            List of deleted file paths.
        """
        cursor = conn.cursor()
        cursor.execute("SELECT id, path FROM files WHERE folder_id = ?;", (folder_id,))
        rows = cursor.fetchall()

        normalized_present = {normalize_file_path(p) for p in present_paths}
        deleted_paths: List[str] = []

        for row in rows:
            if row["path"] not in normalized_present:
                deleted_paths.append(row["path"])
                cursor.execute("DELETE FROM files WHERE id = ?;", (row["id"],))

        cursor.close()
        return deleted_paths

    @staticmethod
    def count_total(conn: sqlite3.Connection) -> int:
        """Count total tracked files."""
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM files;")
        total = cursor.fetchone()[0]
        cursor.close()
        return total

    @staticmethod
    def count_by_status(conn: sqlite3.Connection) -> dict:
        """Count files grouped by extraction status."""
        cursor = conn.cursor()
        cursor.execute("SELECT status, COUNT(*) FROM files GROUP BY status;")
        counts = {row[0]: row[1] for row in cursor.fetchall()}
        cursor.close()
        return counts

    @staticmethod
    def get_total_size_bytes(conn: sqlite3.Connection) -> int:
        """Calculate total size of all tracked files in bytes."""
        cursor = conn.cursor()
        cursor.execute("SELECT COALESCE(SUM(size_bytes), 0) FROM files;")
        total_size = cursor.fetchone()[0]
        cursor.close()
        return total_size

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> FileRecord:
        return FileRecord(
            id=row["id"],
            folder_id=row["folder_id"],
            path=row["path"],
            filename=row["filename"],
            extension=row["extension"],
            file_type=row["file_type"],
            sha256=row["sha256"],
            size_bytes=row["size_bytes"],
            modified_at=row["modified_at"],
            indexed_at=row["indexed_at"],
            status=row["status"],
            error_message=row["error_message"],
            metadata_json=row["metadata_json"],
        )

