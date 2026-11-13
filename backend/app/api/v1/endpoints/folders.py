"""Folder management API endpoints."""

from typing import List, Optional
from fastapi import APIRouter, Body, Depends, Query, Request, status

from app.core.config import get_settings
from app.database.connection import DatabaseConnectionManager
from app.embeddings.configuration import EmbeddingConfig
from app.embeddings.embedder import EmbeddingGemmaEmbedder
from app.schemas.folder import (
    FolderCreateRequest,
    FolderDeleteResponse,
    FolderListResponse,
    FolderResponse,
    FolderUpdateRequest,
)
from app.schemas.indexing import IndexJobResponse, IndexTriggerRequest
from app.services.folder_service import FolderService
from app.services.indexer import IndexingService
from app.services.semantic_pipeline import SemanticPipeline
from app.vector_store.chroma import ChromaVectorStore

router = APIRouter()


def get_folder_service(request: Request) -> FolderService:
    """Dependency providing configured FolderService instance."""
    db = DatabaseConnectionManager()
    settings = get_settings()
    vector_store = ChromaVectorStore(persist_dir=settings.vectors_dir)
    resolved_model = settings.resolved_embedding_model
    config = EmbeddingConfig(
        model_id=resolved_model,
        dimension=settings.embedding_dimension,
        batch_size=settings.embedding_batch_size,
        fetch_pool_size=settings.embedding_fetch_pool_size,
        device=settings.embedding_device,
        precision=settings.embedding_precision,
        local_files_only=(resolved_model != settings.embedding_model_id),
    )
    embedder = EmbeddingGemmaEmbedder(config=config)
    semantic_pipeline = SemanticPipeline(
        db=db,
        embedder=embedder,
        vector_store=vector_store,
        batch_size=settings.embedding_batch_size,
        fetch_pool_size=settings.embedding_fetch_pool_size,
    )
    watcher = getattr(request.app.state, "file_watcher", None) if hasattr(request, "app") else None
    return FolderService(db=db, semantic_pipeline=semantic_pipeline, watcher=watcher)


def get_indexing_service(request: Request) -> IndexingService:
    """Dependency providing configured IndexingService instance."""
    if hasattr(request, "app") and getattr(request.app.state, "indexing_service", None):
        return request.app.state.indexing_service

    db = DatabaseConnectionManager()
    settings = get_settings()
    vector_store = ChromaVectorStore(persist_dir=settings.vectors_dir)
    resolved_model = settings.resolved_embedding_model
    config = EmbeddingConfig(
        model_id=resolved_model,
        dimension=settings.embedding_dimension,
        batch_size=settings.embedding_batch_size,
        fetch_pool_size=settings.embedding_fetch_pool_size,
        device=settings.embedding_device,
        precision=settings.embedding_precision,
        local_files_only=(resolved_model != settings.embedding_model_id),
    )
    embedder = EmbeddingGemmaEmbedder(config=config)
    semantic_pipeline = SemanticPipeline(
        db=db,
        embedder=embedder,
        vector_store=vector_store,
        batch_size=settings.embedding_batch_size,
        fetch_pool_size=settings.embedding_fetch_pool_size,
    )
    return IndexingService(db=db, semantic_pipeline=semantic_pipeline)


@router.get(
    "/folders",
    response_model=FolderListResponse,
    summary="List Registered Folders",
    description="Retrieve all folders currently registered for indexing, with file count and size metrics.",
)
async def list_folders(
    service: FolderService = Depends(get_folder_service),
) -> FolderListResponse:
    """List all registered folders with metrics."""
    folders = service.list_folders()
    return FolderListResponse(folders=folders, total_folders=len(folders))


@router.post(
    "/folders",
    response_model=FolderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register Folder",
    description="Register a new local filesystem directory for indexing.",
)
async def register_folder(
    request: FolderCreateRequest,
    service: FolderService = Depends(get_folder_service),
) -> FolderResponse:
    """Register a new folder."""
    return service.register_folder(path=request.path, enabled=request.enabled)


@router.get(
    "/folders/{folder_id}",
    response_model=FolderResponse,
    summary="Get Folder Details",
    description="Retrieve folder registration metadata and indexing metrics by ID.",
)
async def get_folder(
    folder_id: int,
    service: FolderService = Depends(get_folder_service),
) -> FolderResponse:
    """Get single folder details."""
    return service.get_folder(folder_id)


@router.patch(
    "/folders/{folder_id}",
    response_model=FolderResponse,
    summary="Update Folder",
    description="Update folder properties, such as toggling active indexing inclusion.",
)
async def update_folder(
    folder_id: int,
    request: FolderUpdateRequest,
    service: FolderService = Depends(get_folder_service),
) -> FolderResponse:
    """Update folder properties."""
    if request.enabled is not None:
        return service.toggle_folder(folder_id, request.enabled)
    return service.get_folder(folder_id)


@router.delete(
    "/folders/{folder_id}",
    response_model=FolderDeleteResponse,
    summary="Unregister Folder",
    description="Unregister a folder and cascade-delete its indexed files, chunks, and vector store entries.",
)
async def delete_folder(
    folder_id: int,
    service: FolderService = Depends(get_folder_service),
) -> FolderDeleteResponse:
    """Remove folder from indexing."""
    service.delete_folder(folder_id)
    return FolderDeleteResponse(
        success=True,
        folder_id=folder_id,
        message=f"Folder #{folder_id} and associated indexed content successfully removed.",
    )


@router.post(
    "/folders/{folder_id}/index",
    response_model=IndexJobResponse,
    summary="Index Specific Folder",
    description="Trigger indexing for a single registered folder.",
)
async def index_folder(
    folder_id: int,
    request: Optional[IndexTriggerRequest] = Body(default=None),
    force_reindex: Optional[bool] = Query(default=None, description="Force re-indexing of unchanged files"),
    reconcile_deleted: Optional[bool] = Query(default=None, description="Prune deleted files from index"),
    generate_embeddings: Optional[bool] = Query(default=None, description="Generate vector embeddings"),
    background: Optional[bool] = Query(default=None, description="Execute asynchronously in background"),
    indexing_service: IndexingService = Depends(get_indexing_service),
) -> IndexJobResponse:
    """Trigger indexing on specific folder."""
    f_reindex = (
        request.force_reindex
        if request and request.force_reindex is not None
        else (force_reindex if force_reindex is not None else False)
    )
    r_deleted = (
        request.reconcile_deleted
        if request and request.reconcile_deleted is not None
        else (reconcile_deleted if reconcile_deleted is not None else True)
    )
    g_embeddings = (
        request.generate_embeddings
        if request and request.generate_embeddings is not None
        else (generate_embeddings if generate_embeddings is not None else True)
    )
    bg = (
        request.background
        if request and request.background is not None
        else (background if background is not None else False)
    )

    job = indexing_service.trigger_indexing(
        folder_id=folder_id,
        force_reindex=f_reindex,
        reconcile_deleted=r_deleted,
        generate_embeddings=g_embeddings,
        background=bg,
    )
    return IndexJobResponse(
        id=job.id,
        status=job.status,
        total_files=job.total_files,
        processed_files=job.processed_files,
        successful_files=job.successful_files,
        failed_files=job.failed_files,
        skipped_files=job.skipped_files,
        started_at=job.started_at,
        finished_at=job.finished_at,
        error_message=job.error_message,
    )

