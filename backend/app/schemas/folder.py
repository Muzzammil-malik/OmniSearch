"""Pydantic schemas for folder registration and management."""

from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel, Field


class FolderCreateRequest(BaseModel):
    """Payload for registering a new folder for indexing."""

    path: str = Field(..., min_length=1, description="Absolute or relative path to a local directory")
    enabled: bool = Field(default=True, description="Whether this folder is active for indexing")


class FolderUpdateRequest(BaseModel):
    """Payload for updating an existing folder registration."""

    enabled: Optional[bool] = Field(default=None, description="Toggle folder active status for indexing")


class FolderResponse(BaseModel):
    """Folder representation including aggregated document and chunk metrics."""

    id: int = Field(..., description="Unique folder identifier")
    path: str = Field(..., description="Normalized absolute directory path")
    enabled: bool = Field(default=True, description="Whether folder is actively included in indexing")
    created_at: str = Field(..., description="ISO 8601 creation timestamp")
    updated_at: str = Field(..., description="ISO 8601 update timestamp")
    file_count: int = Field(default=0, description="Total files tracked under this folder")
    total_size_bytes: int = Field(default=0, description="Cumulative size of all tracked files in bytes")
    chunk_count: int = Field(default=0, description="Total chunks indexed under this folder")
    last_indexed_at: Optional[str] = Field(default=None, description="ISO 8601 timestamp of most recently indexed file")


class FolderListResponse(BaseModel):
    """Response containing all registered folders."""

    folders: List[FolderResponse] = Field(default_factory=list, description="List of registered folders")
    total_folders: int = Field(..., description="Total number of registered folders")


class FolderDeleteResponse(BaseModel):
    """Response returned upon unregistering a folder."""

    success: bool = Field(..., description="Whether folder was successfully removed")
    folder_id: int = Field(..., description="ID of the removed folder")
    message: str = Field(..., description="Summary confirmation message")

