"""System diagnostics and application status endpoints."""

from fastapi import APIRouter, Depends

from app.api.v1.endpoints.folders import get_indexing_service
from app.core.config import Settings, get_settings
from app.database.connection import DatabaseConnectionManager
from app.schemas.indexing import IndexingStatsResponse
from app.schemas.system import SystemStatusResponse
from app.services.indexer import IndexingService
from app.services.system_service import SystemService

router = APIRouter()


def get_system_service(settings: Settings = Depends(get_settings)) -> SystemService:
    """Dependency providing configured SystemService instance."""
    db = DatabaseConnectionManager()
    return SystemService(db=db, settings=settings)


@router.get(
    "/system/status",
    response_model=SystemStatusResponse,
    summary="System Diagnostic Status",
    description="Retrieve operational telemetry across database, vector store, and local embedding models.",
)
async def get_system_status(
    service: SystemService = Depends(get_system_service),
) -> SystemStatusResponse:
    """Retrieve detailed system and subsystem diagnostics."""
    return service.get_system_status()


@router.get(
    "/system/stats",
    response_model=IndexingStatsResponse,
    summary="System Content Statistics",
    description="Retrieve aggregated statistics on indexed files, chunks, and vector embeddings.",
)
async def get_system_stats(
    indexing_service: IndexingService = Depends(get_indexing_service),
) -> IndexingStatsResponse:
    """Retrieve aggregated indexing statistics."""
    return indexing_service.get_indexing_stats()

