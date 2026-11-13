"""Indexing control and status API endpoints."""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Request

from app.api.v1.endpoints.folders import get_indexing_service
from app.core.exceptions import JobNotFoundError
from app.schemas.indexing import (
    IndexJobResponse,
    IndexTriggerRequest,
    IndexingStatsResponse,
    IndexingStatusResponse,
    WatcherStatusResponse,
)
from app.services.indexer import IndexingService

router = APIRouter()


@router.post(
    "/indexing/start",
    response_model=IndexJobResponse,
    summary="Trigger Indexing",
    description="Trigger indexing for all active registered folders or a specified folder.",
)
async def start_indexing(
    request: IndexTriggerRequest = IndexTriggerRequest(),
    service: IndexingService = Depends(get_indexing_service),
) -> IndexJobResponse:
    """Trigger indexing operation."""
    job = service.trigger_indexing(
        folder_id=request.folder_id,
        folder_path=request.folder_path,
        force_reindex=request.force_reindex,
        reconcile_deleted=request.reconcile_deleted,
        generate_embeddings=request.generate_embeddings,
        background=request.background,
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


@router.get(
    "/indexing/status",
    response_model=IndexingStatusResponse,
    summary="Get Indexing Status",
    description="Inspect whether indexing is actively running and review recent job history.",
)
async def get_indexing_status(
    request: Request,
    service: IndexingService = Depends(get_indexing_service),
) -> IndexingStatusResponse:
    """Inspect current indexing engine status."""
    watcher_status = None
    watcher = getattr(request.app.state, "file_watcher", None) if hasattr(request, "app") else None
    coordinator = getattr(request.app.state, "change_coordinator", None) if hasattr(request, "app") else None
    debouncer = getattr(request.app.state, "change_debouncer", None) if hasattr(request, "app") else None

    if watcher or coordinator:
        watcher_status = WatcherStatusResponse(
            enabled=True,
            active=watcher.is_running if watcher else False,
            watched_folders=watcher.watched_folders if watcher else [],
            pending_events=debouncer.pending_count if debouncer else 0,
            coordinator_queue_size=coordinator.queue_size if coordinator else 0,
            processed_events=coordinator.processed_count if coordinator else 0,
            current_file=coordinator.current_file if coordinator else None,
        )

    status_response = service.get_indexing_status()
    if watcher_status is not None:
        status_response.watcher = watcher_status
    return status_response


@router.get(
    "/indexing/watcher",
    response_model=WatcherStatusResponse,
    summary="Get Watcher Status",
    description="Inspect real-time filesystem watcher activity, queues, and watched folders.",
)
async def get_watcher_status(
    request: Request,
) -> WatcherStatusResponse:
    """Inspect filesystem watcher and event coordinator telemetry."""
    watcher = getattr(request.app.state, "file_watcher", None) if hasattr(request, "app") else None
    coordinator = getattr(request.app.state, "change_coordinator", None) if hasattr(request, "app") else None
    debouncer = getattr(request.app.state, "change_debouncer", None) if hasattr(request, "app") else None

    return WatcherStatusResponse(
        enabled=watcher is not None,
        active=watcher.is_running if watcher else False,
        watched_folders=watcher.watched_folders if watcher else [],
        pending_events=debouncer.pending_count if debouncer else 0,
        coordinator_queue_size=coordinator.queue_size if coordinator else 0,
        processed_events=coordinator.processed_count if coordinator else 0,
        current_file=coordinator.current_file if coordinator else None,
    )


@router.get(
    "/indexing/jobs",
    response_model=List[IndexJobResponse],
    summary="List Recent Indexing Jobs",
    description="Retrieve a list of recent indexing execution logs and outcomes.",
)
async def list_indexing_jobs(
    limit: int = Query(default=20, ge=1, le=100, description="Max jobs to return"),
    service: IndexingService = Depends(get_indexing_service),
) -> List[IndexJobResponse]:
    """List recent indexing jobs."""
    jobs = service.list_recent_jobs(limit=limit)
    return [
        IndexJobResponse(
            id=j.id,
            status=j.status,
            total_files=j.total_files,
            processed_files=j.processed_files,
            successful_files=j.successful_files,
            failed_files=j.failed_files,
            skipped_files=j.skipped_files,
            started_at=j.started_at,
            finished_at=j.finished_at,
            error_message=j.error_message,
        )
        for j in jobs
        if j.id is not None
    ]


@router.get(
    "/indexing/jobs/{job_id}",
    response_model=IndexJobResponse,
    summary="Get Indexing Job by ID",
    description="Retrieve execution details and metrics for a specific indexing job.",
)
async def get_indexing_job(
    job_id: int,
    service: IndexingService = Depends(get_indexing_service),
) -> IndexJobResponse:
    """Get indexing job by ID."""
    job = service.get_job(job_id)
    if not job:
        raise JobNotFoundError(job_id)
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


@router.get(
    "/indexing/stats",
    response_model=IndexingStatsResponse,
    summary="Get Indexing Statistics",
    description="Retrieve global aggregated counts across folders, files, chunks, and vector embeddings.",
)
async def get_indexing_stats(
    service: IndexingService = Depends(get_indexing_service),
) -> IndexingStatsResponse:
    """Get aggregated indexing statistics."""
    return service.get_indexing_stats()

