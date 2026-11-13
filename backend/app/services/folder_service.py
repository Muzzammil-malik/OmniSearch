"""Folder service for managing registered folders and folder metadata."""

from pathlib import Path
from typing import Any, List, Optional

from app.core.exceptions import (
    DuplicateFolderError,
    FolderNotFoundError,
    InvalidFolderPathError,
)
from app.core.logging import get_logger
from app.database.connection import DatabaseConnectionManager
from app.database.repositories.folders import FolderRepository, normalize_folder_path
from app.schemas.folder import FolderResponse

logger = get_logger(__name__)


class FolderService:
    """Application service orchestrating folder registration, status, and removal."""

    def __init__(
        self,
        db: DatabaseConnectionManager,
        semantic_pipeline: Optional[Any] = None,
        watcher: Optional[Any] = None,
    ) -> None:
        self.db = db
        self.semantic_pipeline = semantic_pipeline
        self.watcher = watcher

    def register_folder(self, path: str, enabled: bool = True) -> FolderResponse:
        """Register a new folder path for indexing.

        Args:
            path: Target directory path string.
            enabled: Initial enabled status.

        Returns:
            FolderResponse containing the registered folder and initial statistics.

        Raises:
            InvalidFolderPathError: If path does not exist or is not a directory.
            DuplicateFolderError: If path is already registered.
        """
        raw_path = Path(path)
        try:
            resolved_path = raw_path.resolve()
        except Exception as exc:
            raise InvalidFolderPathError(path, reason=str(exc))

        if not resolved_path.exists():
            raise InvalidFolderPathError(str(resolved_path), reason="Directory does not exist on disk")
        if not resolved_path.is_dir():
            raise InvalidFolderPathError(str(resolved_path), reason="Path is a file, not a directory")

        norm_path = normalize_folder_path(str(resolved_path))

        with self.db.transaction() as conn:
            existing = FolderRepository.get_by_path(conn, norm_path)
            if existing:
                raise DuplicateFolderError(norm_path)

            record = FolderRepository.get_or_create(conn, norm_path)
            if not enabled and record.id is not None:
                FolderRepository.update_enabled(conn, record.id, False)

            assert record.id is not None
            stats = FolderRepository.get_folder_stats(conn, record.id)

        assert stats is not None
        if enabled and self.watcher and record.id is not None:
            try:
                self.watcher.add_folder(record.id, record.path)
            except Exception as exc:
                logger.warning("Could not register folder #%d with watcher: %s", record.id, exc)

        logger.info("Successfully registered folder #%d: %s", record.id, norm_path)
        return FolderResponse(**stats)

    def list_folders(self) -> List[FolderResponse]:
        """List all registered folders with their aggregated file, chunk, and size metrics."""
        with self.db.connection() as conn:
            stats_list = FolderRepository.list_all_with_stats(conn)
        return [FolderResponse(**s) for s in stats_list]

    def get_folder(self, folder_id: int) -> FolderResponse:
        """Fetch folder by identifier.

        Raises:
            FolderNotFoundError: If folder_id does not exist.
        """
        with self.db.connection() as conn:
            stats = FolderRepository.get_folder_stats(conn, folder_id)

        if not stats:
            raise FolderNotFoundError(folder_id)
        return FolderResponse(**stats)

    def toggle_folder(self, folder_id: int, enabled: bool) -> FolderResponse:
        """Update enabled status for a registered folder.

        Raises:
            FolderNotFoundError: If folder_id does not exist.
        """
        with self.db.transaction() as conn:
            folder = FolderRepository.get_by_id(conn, folder_id)
            if not folder:
                raise FolderNotFoundError(folder_id)

            FolderRepository.update_enabled(conn, folder_id, enabled)
            stats = FolderRepository.get_folder_stats(conn, folder_id)

        assert stats is not None
        if self.watcher:
            try:
                if enabled:
                    self.watcher.add_folder(folder_id, folder.path)
                else:
                    self.watcher.remove_folder(folder_id)
            except Exception as exc:
                logger.warning("Could not update watcher for folder #%d: %s", folder_id, exc)

        logger.info("Updated folder #%d enabled=%s", folder_id, enabled)
        return FolderResponse(**stats)

    def delete_folder(self, folder_id: int) -> bool:
        """Unregister folder and cascade-delete its files, chunks, and vector index entries.

        Raises:
            FolderNotFoundError: If folder_id does not exist.
        """
        if self.watcher:
            try:
                self.watcher.remove_folder(folder_id)
            except Exception as exc:
                logger.warning("Could not remove folder #%d from watcher: %s", folder_id, exc)

        with self.db.transaction() as conn:
            folder = FolderRepository.get_by_id(conn, folder_id)
            if not folder:
                raise FolderNotFoundError(folder_id)

            deleted = FolderRepository.delete(conn, folder_id)

        # Reconcile vector store to remove dangling vectors
        if self.semantic_pipeline:
            try:
                self.semantic_pipeline.reconcile_vector_store()
            except Exception as exc:
                logger.warning("Vector store reconciliation warning after folder deletion: %s", exc)

        logger.info("Deleted folder #%d: %s", folder_id, folder.path)
        return deleted
