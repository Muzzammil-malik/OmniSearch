"""System status service for diagnosing application health and backend subsystems."""

from datetime import datetime, timezone
import os
from pathlib import Path
from typing import Optional

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.database.connection import DatabaseConnectionManager
from app.database.repositories.chunks import ChunkRepository
from app.database.repositories.embeddings import ChunkEmbeddingRepository
from app.database.repositories.files import FileRepository
from app.database.repositories.folders import FolderRepository
from app.embeddings.model_manager import EmbeddingModelManager
from app.schemas.system import (
    DatabaseStatus,
    EmbeddingModelStatus,
    SystemStatusResponse,
    VectorStoreStatus,
)
from app.vector_store.chroma import ChromaVectorStore

logger = get_logger(__name__)


class SystemService:
    """Provides unified system diagnostic status without eagerly loading heavy AI models into RAM."""

    def __init__(
        self,
        db: DatabaseConnectionManager,
        settings: Optional[Settings] = None,
        vector_store: Optional[ChromaVectorStore] = None,
    ) -> None:
        self.db = db
        self.settings = settings or get_settings()
        self._vector_store = vector_store

    @property
    def vector_store(self) -> ChromaVectorStore:
        if self._vector_store is None:
            self._vector_store = ChromaVectorStore(persist_dir=self.settings.vectors_dir)
        return self._vector_store

    def get_system_status(self) -> SystemStatusResponse:
        """Collect diagnostic telemetry across database, vector store, and embedding models."""
        db_status = self._get_database_status()
        vs_status = self._get_vector_store_status()
        model_status = self._get_embedding_model_status()

        overall_status = "healthy" if db_status.status == "healthy" else "degraded"

        return SystemStatusResponse(
            app_name=self.settings.app_name,
            version=self.settings.app_version,
            environment=self.settings.environment,
            status=overall_status,
            database=db_status,
            vector_store=vs_status,
            embedding_model=model_status,
            timestamp=datetime.now(timezone.utc),
        )

    def _get_database_status(self) -> DatabaseStatus:
        db_path = self.settings.resolved_db_path
        status = "healthy"
        wal_mode = True
        total_folders = 0
        total_files = 0
        total_chunks = 0

        try:
            with self.db.connection() as conn:
                cursor = conn.cursor()
                cursor.execute("PRAGMA journal_mode;")
                mode_row = cursor.fetchone()
                if mode_row:
                    wal_mode = mode_row[0].lower() == "wal"
                cursor.close()

                total_folders = len(FolderRepository.list_all(conn))
                total_files = FileRepository.count_total(conn)
                total_chunks = ChunkRepository.count_total(conn)
        except Exception as exc:
            logger.error("Database status check failed: %s", exc)
            status = "unavailable"

        size_bytes: Optional[int] = None
        if isinstance(db_path, Path) and db_path.exists():
            try:
                size_bytes = db_path.stat().st_size
            except Exception:
                size_bytes = None

        return DatabaseStatus(
            status=status,
            path=str(db_path),
            wal_mode=wal_mode,
            total_folders=total_folders,
            total_files=total_files,
            total_chunks=total_chunks,
            size_bytes=size_bytes,
        )

    def _get_vector_store_status(self) -> VectorStoreStatus:
        persist_dir = str(self.settings.vectors_dir)
        status = "available"
        total_vectors = 0
        unembedded = 0

        try:
            total_vectors = self.vector_store.count()
            if total_vectors == 0:
                status = "empty"
        except Exception as exc:
            logger.warning("ChromaDB vector store check warning: %s", exc)
            status = "unavailable"

        try:
            with self.db.connection() as conn:
                unembedded = ChunkEmbeddingRepository.count_unembedded(conn)
        except Exception as exc:
            logger.warning("Unembedded chunks count warning: %s", exc)

        return VectorStoreStatus(
            status=status,
            collection_name=self.vector_store.collection_name,
            total_vectors=total_vectors,
            unembedded_chunks=unembedded,
            persist_dir=persist_dir,
        )

    def _get_embedding_model_status(self) -> EmbeddingModelStatus:
        local_dir = self.settings.models_dir / "embeddinggemma-2"
        local_weights_present = (
            local_dir.exists() and (local_dir / "model.safetensors").exists()
        )

        manager = EmbeddingModelManager.get_instance()
        is_loaded = manager.is_loaded

        if is_loaded:
            status = "loaded"
        elif local_weights_present:
            status = "ready"
        else:
            status = "weights_missing"

        return EmbeddingModelStatus(
            status=status,
            model_id=self.settings.resolved_embedding_model,
            dimension=self.settings.embedding_dimension,
            device=self.settings.embedding_device,
            is_loaded=is_loaded,
            local_weights_present=local_weights_present,
        )

