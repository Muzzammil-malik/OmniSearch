"""Pydantic schemas for system status, database health, and subsystem availability."""

from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field


class DatabaseStatus(BaseModel):
    """Health and metric summary of the canonical SQLite database."""

    status: str = Field(..., description="Operational status: 'healthy', 'degraded', 'unavailable'")
    path: str = Field(..., description="Database file path on local filesystem")
    wal_mode: bool = Field(default=True, description="Whether WAL mode is active")
    total_folders: int = Field(default=0, description="Total registered folders")
    total_files: int = Field(default=0, description="Total files tracked in database")
    total_chunks: int = Field(default=0, description="Total document chunks in database")
    size_bytes: Optional[int] = Field(default=None, description="Size of database file on disk in bytes")


class VectorStoreStatus(BaseModel):
    """Availability and metrics of local ChromaDB vector store."""

    status: str = Field(..., description="Operational status: 'available', 'empty', 'unavailable'")
    collection_name: str = Field(..., description="Active ChromaDB collection name")
    total_vectors: int = Field(default=0, description="Total embedded vectors stored in collection")
    unembedded_chunks: int = Field(default=0, description="Chunks in SQLite awaiting vector generation")
    persist_dir: str = Field(..., description="ChromaDB storage directory path")
    error_message: Optional[str] = Field(default=None, description="Error details if vector store is unavailable")
    error_category: Optional[str] = Field(default=None, description="Diagnostic category of failure (e.g. application_control_policy_blocked)")


class EmbeddingModelStatus(BaseModel):
    """Status and availability of the local EmbeddingGemma 2 model."""

    status: str = Field(..., description="Model readiness: 'ready', 'weights_missing', 'loaded', 'dependency_unavailable'")
    model_id: str = Field(..., description="Resolved model identifier or local weights path")
    dimension: int = Field(..., description="Embedding dimension")
    device: str = Field(..., description="Target execution device ('cpu' or 'cuda')")
    is_loaded: bool = Field(default=False, description="Whether model weights are actively resident in RAM")
    local_weights_present: bool = Field(default=False, description="Whether verified weights exist on disk")
    error_message: Optional[str] = Field(default=None, description="Error details if model dependency failed")
    error_category: Optional[str] = Field(default=None, description="Diagnostic category of failure (e.g. application_control_policy_blocked)")


class SystemStatusResponse(BaseModel):
    """Unified system status report for application diagnostics and frontend settings."""

    app_name: str = Field(..., description="Application name")
    version: str = Field(..., description="Application semantic version")
    environment: str = Field(..., description="Runtime environment")
    status: str = Field(..., description="Overall system health status: 'healthy' or 'degraded'")
    database: DatabaseStatus = Field(..., description="SQLite database diagnostics")
    vector_store: VectorStoreStatus = Field(..., description="ChromaDB vector store diagnostics")
    embedding_model: EmbeddingModelStatus = Field(..., description="Embedding model diagnostics")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of the status check",
    )


class NativeFolderPickerResponse(BaseModel):
    """Result of native operating-system folder selection dialog."""

    path: Optional[str] = Field(default=None, description="Selected absolute directory path, or None if canceled")
    canceled: bool = Field(default=False, description="Whether the user canceled or dismissed the picker dialog")
    error: Optional[str] = Field(default=None, description="Error message if native dialog could not be invoked")


class FileActionRequest(BaseModel):
    """Request to perform an OS-level file operation."""

    path: str = Field(..., min_length=1, description="Absolute file path on host system")


class FileActionResponse(BaseModel):
    """Result of an OS-level file operation."""

    success: bool = Field(..., description="Whether action succeeded")
    error: Optional[str] = Field(default=None, description="Error message if operation failed")


class ContextMenuStatusResponse(BaseModel):
    """Current registration state of Windows Explorer context menu."""

    enabled: bool = Field(..., description="Whether context menu integration is registered")


class ContextMenuToggleRequest(BaseModel):
    """Request to enable or disable Windows Explorer context menu."""

    enabled: bool = Field(..., description="Target registration state")


class ContextMenuToggleResponse(BaseModel):
    """Result of Windows Explorer context menu registration/unregistration."""

    success: bool = Field(..., description="Whether operation succeeded")
    error: Optional[str] = Field(default=None, description="Error message if operation failed")



