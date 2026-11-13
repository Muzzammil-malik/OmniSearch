"""Central v1 API router assembling all v1 resource endpoints."""

from fastapi import APIRouter
from app.api.v1.endpoints import folders, health, indexing, search, system

api_router = APIRouter()
api_router.include_router(health.router, tags=["Health"])
api_router.include_router(folders.router, tags=["Folders"])
api_router.include_router(indexing.router, tags=["Indexing"])
api_router.include_router(search.router, tags=["Search"])
api_router.include_router(system.router, tags=["System"])
