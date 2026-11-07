"""Lightweight startup and on-demand filesystem reconciliation."""

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set
from app.core.logging import get_logger
from app.database.connection import DatabaseConnectionManager
from app.database.repositories.files import FileRepository, normalize_file_path
from app.database.repositories.folders import FolderRepository
from app.ingestion.hashing import try_calculate_sha256
from app.ingestion.scanner import FolderScanner
from app.watcher.events import FileChangeEvent, FileChangeType

logger = get_logger(__name__)


@dataclass
class ReconciliationSummary:
    """Statistics captured during a folder reconciliation pass."""

    folder_id: int
    folder_path: str
    created_count: int = 0
    modified_count: int = 0
    deleted_count: int = 0
    unchanged_count: int = 0
    duration_seconds: float = 0.0

    @property
    def created_files(self) -> int:
        return self.created_count

    @property
    def modified_files(self) -> int:
        return self.modified_count

    @property
    def deleted_files(self) -> int:
        return self.deleted_count

    @property
    def unmodified_files(self) -> int:
        return self.unchanged_count

    @property
    def checked_files(self) -> int:
        return self.created_count + self.modified_count + self.deleted_count + self.unchanged_count


class StartupReconciler:
    """Lightweight drift reconciler that diffs filesystem against SQLite without full re-indexing."""

    def __init__(
        self,
        db: DatabaseConnectionManager,
        on_change: Optional[Callable[[FileChangeEvent], None]] = None,
        indexing_service: Optional[Any] = None,
        scanner: Optional[FolderScanner] = None,
    ) -> None:
        self.db = db
        self.indexing_service = indexing_service
        self.scanner = scanner or FolderScanner()

        if on_change is not None:
            self.on_change = on_change
        elif indexing_service is not None:
            def _default_on_change(ev: FileChangeEvent) -> None:
                if ev.change_type in (FileChangeType.CREATED, FileChangeType.MODIFIED):
                    indexing_service.index_single_file(ev.path, generate_embeddings=True)
                elif ev.change_type == FileChangeType.DELETED:
                    indexing_service.delete_single_file(ev.path)
            self.on_change = _default_on_change
        else:
            self.on_change = lambda ev: None

    def reconcile_folder(self, folder_id: int, folder_path: Path) -> ReconciliationSummary:
        """Perform a metadata-first diff between disk files and SQLite records for a folder."""
        import time
        start_time = time.perf_counter()
        summary = ReconciliationSummary(folder_id=folder_id, folder_path=str(folder_path))

        resolved_path = Path(folder_path).resolve()
        if not resolved_path.exists() or not resolved_path.is_dir():
            logger.warning("Reconciliation target does not exist on disk: %s", resolved_path)
            return summary

        # 1. Fetch existing tracked files from SQLite
        with self.db.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, path, size_bytes, modified_at, sha256, status
                FROM files
                WHERE folder_id = ?;
                """,
                (folder_id,),
            )
            rows = cursor.fetchall()
            cursor.close()

        db_files: Dict[str, dict] = {
            r["path"]: {
                "id": r["id"],
                "size_bytes": r["size_bytes"],
                "modified_at": r["modified_at"],
                "sha256": r["sha256"],
                "status": r["status"],
            }
            for r in rows
        }

        # 2. Discover supported files on disk using the scanner
        scan_report = self.scanner.scan(resolved_path)
        disk_files = {
            normalize_file_path(str(sf.path)): sf
            for sf in scan_report.supported_files
        }

        # 3. Identify deleted files (in SQLite, missing on disk)
        deleted_paths = set(db_files.keys()) - set(disk_files.keys())
        for dp in deleted_paths:
            summary.deleted_count += 1
            self.on_change(FileChangeEvent(change_type=FileChangeType.DELETED, path=Path(dp)))

        # 4. Identify new files (on disk, missing in SQLite)
        new_paths = set(disk_files.keys()) - set(db_files.keys())
        for np in new_paths:
            summary.created_count += 1
            self.on_change(FileChangeEvent(change_type=FileChangeType.CREATED, path=disk_files[np].path))

        # 5. Identify modified files using fast metadata check first
        common_paths = set(disk_files.keys()) & set(db_files.keys())
        for cp in common_paths:
            sf = disk_files[cp]
            rec = db_files[cp]

            try:
                stat_res = sf.path.stat()
                disk_size = stat_res.st_size
                disk_mtime_iso = datetime.fromtimestamp(stat_res.st_mtime, tz=timezone.utc).isoformat()
            except OSError:
                continue

            # Fast path: If size and mtime are unchanged, file is untouched -> do NOT hash
            if disk_size == rec["size_bytes"] and disk_mtime_iso == rec["modified_at"] and rec["status"] == "success":
                summary.unchanged_count += 1
                continue

            # Metadata differed: perform SHA-256 hash check to verify if content actually changed
            current_hash = try_calculate_sha256(sf.path)
            if current_hash is not None and current_hash == rec["sha256"] and rec["status"] == "success":
                # Content identical, only mtime/stat changed -> update SQLite metadata without re-indexing
                summary.unchanged_count += 1
                with self.db.transaction() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "UPDATE files SET modified_at = ?, size_bytes = ? WHERE id = ?;",
                        (disk_mtime_iso, disk_size, rec["id"]),
                    )
                    cursor.close()
                continue

            # Content genuinely changed
            summary.modified_count += 1
            self.on_change(FileChangeEvent(change_type=FileChangeType.MODIFIED, path=sf.path))

        summary.duration_seconds = round(time.perf_counter() - start_time, 3)
        logger.info(
            "Reconciliation complete for '%s' in %.3fs (New: %d, Modified: %d, Deleted: %d, Unchanged: %d)",
            resolved_path.name,
            summary.duration_seconds,
            summary.created_count,
            summary.modified_count,
            summary.deleted_count,
            summary.unchanged_count,
        )
        return summary

    def reconcile_all_active_folders(self) -> List[ReconciliationSummary]:
        """Perform reconciliation across all enabled registered folders."""
        with self.db.connection() as conn:
            folders = FolderRepository.list_all(conn)

        summaries: List[ReconciliationSummary] = []
        for f in folders:
            if f.enabled and f.id is not None:
                summaries.append(self.reconcile_folder(f.id, Path(f.path)))

        return summaries

