"""Folder repository for tracking indexed root folders."""

from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from typing import List, Optional
from app.schemas.processing import FolderRecord


def normalize_folder_path(path: str) -> str:
    """Normalize directory path string for consistent database uniqueness."""
    return str(Path(path).resolve())


class FolderRepository:
    """Data access repository for folders table."""

    @staticmethod
    def get_or_create(conn: sqlite3.Connection, path: str) -> FolderRecord:
        """Retrieve existing folder record or create a new one."""
        normalized = normalize_folder_path(path)
        cursor = conn.cursor()

        cursor.execute("SELECT id, path, enabled, created_at, updated_at FROM folders WHERE path = ?;", (normalized,))
        row = cursor.fetchone()
        if row:
            cursor.close()
            return FolderRecord(
                id=row["id"],
                path=row["path"],
                enabled=bool(row["enabled"]),
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )

        now_iso = datetime.now(timezone.utc).isoformat()
        cursor.execute(
            """
            INSERT INTO folders (path, enabled, created_at, updated_at)
            VALUES (?, 1, ?, ?);
            """,
            (normalized, now_iso, now_iso),
        )
        folder_id = cursor.lastrowid
        cursor.close()

        return FolderRecord(
            id=folder_id,
            path=normalized,
            enabled=True,
            created_at=now_iso,
            updated_at=now_iso,
        )

    @staticmethod
    def get_by_id(conn: sqlite3.Connection, folder_id: int) -> Optional[FolderRecord]:
        """Fetch folder by primary key ID."""
        cursor = conn.cursor()
        cursor.execute("SELECT id, path, enabled, created_at, updated_at FROM folders WHERE id = ?;", (folder_id,))
        row = cursor.fetchone()
        cursor.close()
        if not row:
            return None
        return FolderRecord(
            id=row["id"],
            path=row["path"],
            enabled=bool(row["enabled"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def list_all(conn: sqlite3.Connection) -> List[FolderRecord]:
        """List all registered folders."""
        cursor = conn.cursor()
        cursor.execute("SELECT id, path, enabled, created_at, updated_at FROM folders ORDER BY id ASC;")
        rows = cursor.fetchall()
        cursor.close()
        return [
            FolderRecord(
                id=r["id"],
                path=r["path"],
                enabled=bool(r["enabled"]),
                created_at=r["created_at"],
                updated_at=r["updated_at"],
            )
            for r in rows
        ]

    @staticmethod
    def list_active(conn: sqlite3.Connection) -> List[FolderRecord]:
        """List all active (enabled=1) registered folders."""
        cursor = conn.cursor()
        cursor.execute("SELECT id, path, enabled, created_at, updated_at FROM folders WHERE enabled = 1 ORDER BY id ASC;")
        rows = cursor.fetchall()
        cursor.close()
        return [
            FolderRecord(
                id=r["id"],
                path=r["path"],
                enabled=bool(r["enabled"]),
                created_at=r["created_at"],
                updated_at=r["updated_at"],
            )
            for r in rows
        ]

    @staticmethod
    def delete(conn: sqlite3.Connection, folder_id: int) -> bool:
        """Delete a folder record. Foreign-key CASCADE deletes associated files and chunks."""
        cursor = conn.cursor()
        cursor.execute("DELETE FROM folders WHERE id = ?;", (folder_id,))
        deleted = cursor.rowcount > 0
        cursor.close()
        return deleted

    @staticmethod
    def get_by_path(conn: sqlite3.Connection, path: str) -> Optional[FolderRecord]:
        """Fetch folder by directory path."""
        normalized = normalize_folder_path(path)
        cursor = conn.cursor()
        cursor.execute("SELECT id, path, enabled, created_at, updated_at FROM folders WHERE path = ?;", (normalized,))
        row = cursor.fetchone()
        cursor.close()
        if not row:
            return None
        return FolderRecord(
            id=row["id"],
            path=row["path"],
            enabled=bool(row["enabled"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def update_enabled(conn: sqlite3.Connection, folder_id: int, enabled: bool) -> bool:
        """Update folder enabled state."""
        now_iso = datetime.now(timezone.utc).isoformat()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE folders SET enabled = ?, updated_at = ? WHERE id = ?;",
            (1 if enabled else 0, now_iso, folder_id),
        )
        updated = cursor.rowcount > 0
        cursor.close()
        return updated

    @staticmethod
    def find_matching_folder(conn: sqlite3.Connection, file_path: str) -> Optional[FolderRecord]:
        """Find the most specific active folder containing the given file path."""
        norm_file = normalize_folder_path(file_path).lower()
        all_folders = FolderRepository.list_all(conn)
        matching: List[FolderRecord] = []
        for f in all_folders:
            if not f.enabled:
                continue
            norm_folder = normalize_folder_path(f.path).lower()
            if norm_file == norm_folder or norm_file.startswith(norm_folder + "\\") or norm_file.startswith(norm_folder + "/"):
                matching.append(f)
        if not matching:
            return None
        # Return most specific (longest path)
        matching.sort(key=lambda x: len(x.path), reverse=True)
        return matching[0]

    @staticmethod
    def get_folder_stats(conn: sqlite3.Connection, folder_id: int) -> Optional[dict]:
        """Fetch folder record along with aggregated file and chunk counts."""
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT f.id, f.path, f.enabled, f.created_at, f.updated_at,
                   (SELECT COUNT(*) FROM files WHERE folder_id = f.id) AS file_count,
                   (SELECT COALESCE(SUM(size_bytes), 0) FROM files WHERE folder_id = f.id) AS total_size_bytes,
                   (SELECT COUNT(*) FROM chunks c JOIN files fi ON c.file_id = fi.id WHERE fi.folder_id = f.id) AS chunk_count,
                   (SELECT MAX(indexed_at) FROM files WHERE folder_id = f.id) AS last_indexed_at
            FROM folders f
            WHERE f.id = ?;
            """,
            (folder_id,),
        )
        row = cursor.fetchone()
        cursor.close()
        if not row:
            return None
        return {
            "id": row["id"],
            "path": row["path"],
            "enabled": bool(row["enabled"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "file_count": row["file_count"],
            "total_size_bytes": row["total_size_bytes"],
            "chunk_count": row["chunk_count"],
            "last_indexed_at": row["last_indexed_at"],
        }

    @staticmethod
    def list_all_with_stats(conn: sqlite3.Connection) -> List[dict]:
        """List all registered folders with aggregated metrics."""
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT f.id, f.path, f.enabled, f.created_at, f.updated_at,
                   (SELECT COUNT(*) FROM files WHERE folder_id = f.id) AS file_count,
                   (SELECT COALESCE(SUM(size_bytes), 0) FROM files WHERE folder_id = f.id) AS total_size_bytes,
                   (SELECT COUNT(*) FROM chunks c JOIN files fi ON c.file_id = fi.id WHERE fi.folder_id = f.id) AS chunk_count,
                   (SELECT MAX(indexed_at) FROM files WHERE folder_id = f.id) AS last_indexed_at
            FROM folders f
            ORDER BY f.id ASC;
            """
        )
        rows = cursor.fetchall()
        cursor.close()
        return [
            {
                "id": r["id"],
                "path": r["path"],
                "enabled": bool(r["enabled"]),
                "created_at": r["created_at"],
                "updated_at": r["updated_at"],
                "file_count": r["file_count"],
                "total_size_bytes": r["total_size_bytes"],
                "chunk_count": r["chunk_count"],
                "last_indexed_at": r["last_indexed_at"],
            }
            for r in rows
        ]
