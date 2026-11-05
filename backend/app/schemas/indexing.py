"""Pydantic schemas for indexing lifecycle controls and statistics."""

from typing import List, Optional
from pydantic import BaseModel, Field

from app.schemas.processing import IndexJobStatus


class IndexTriggerRequest(BaseModel):
    """Payload for triggering an indexing operation."""

    folder_id: Optional[int] = Field(default=None, description="Optional folder ID to index specifically")
    folder_path: Optional[str] = Field(default=None, description="Optional folder path to register and index")
    force_reindex: bool = Field(default=False, description="Force re-extraction even if SHA-256 matches")
    reconcile_deleted: bool = Field(default=True, description="Reconcile and prune files removed from disk")
    generate_embeddings: bool = Field(default=True, description="Generate semantic embeddings for new chunks")
    background: bool = Field(default=False, description="Run indexing asynchronously in background")


class IndexJobResponse(BaseModel):
    """Representation of an indexing job record."""

    id: int = Field(..., description="Unique job identifier")
    status: IndexJobStatus = Field(..., description="Current job lifecycle status")
    total_files: int = Field(default=0, description="Total supported files discovered")
    processed_files: int = Field(default=0, description="Files processed so far")
    successful_files: int = Field(default=0, description="Files successfully indexed")
    failed_files: int = Field(default=0, description="Files that encountered extraction or chunking errors")
    skipped_files: int = Field(default=0, description="Files skipped because content was unchanged")
    started_at: str = Field(..., description="ISO 8601 job start timestamp")
    finished_at: Optional[str] = Field(default=None, description="ISO 8601 job completion timestamp")
    error_message: Optional[str] = Field(default=None, description="Optional failure reason")


class IndexingStatusResponse(BaseModel):
    """Status overview of the indexing engine and recent operations."""

    is_indexing: bool = Field(..., description="Whether an indexing job is currently actively running")
    current_job: Optional[IndexJobResponse] = Field(default=None, description="Currently running job if any")
    recent_jobs: List[IndexJobResponse] = Field(default_factory=list, description="Recent indexing jobs")


class IndexingStatsResponse(BaseModel):
    """Aggregated global metrics across all indexed content."""

    total_folders: int = Field(default=0, description="Total registered folders")
    total_files: int = Field(default=0, description="Total tracked files")
    successful_files: int = Field(default=0, description="Total successfully indexed files")
    failed_files: int = Field(default=0, description="Files with extraction or processing errors")
    total_chunks: int = Field(default=0, description="Total persistent document chunks")
    embedded_chunks: int = Field(default=0, description="Total chunks with ChromaDB vector embeddings")
    unembedded_chunks: int = Field(default=0, description="Chunks pending embedding generation")
    total_size_bytes: int = Field(default=0, description="Cumulative size of all tracked files in bytes")
