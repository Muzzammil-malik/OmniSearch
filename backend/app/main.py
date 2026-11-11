"""OmniSearch backend application entry point."""

from contextlib import asynccontextmanager
from datetime import datetime, timezone
import os
import sys
from threading import Thread
from typing import AsyncGenerator, Optional
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
import uvicorn

from app.api.v1.router import api_router
from app.core.config import Settings, get_settings
from app.core.exceptions import OmniSearchException
from app.core.logging import get_logger, setup_logging
from app.database.connection import DatabaseConnectionManager
from app.database.initialization import init_db
from app.database.repositories.folders import FolderRepository
from app.embeddings.configuration import EmbeddingConfig
from app.embeddings.embedder import EmbeddingGemmaEmbedder
from app.services.change_coordinator import ChangeCoordinator
from app.services.indexer import IndexingService
from app.services.semantic_pipeline import SemanticPipeline
from app.vector_store.chroma import ChromaVectorStore
from app.watcher.debouncer import ChangeDebouncer
from app.watcher.reconciler import StartupReconciler
from app.watcher.service import FileSystemWatcher

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application startup and shutdown lifecycle events."""
    settings = get_settings()
    setup_logging(settings.log_level)
    logger.info("Starting %s v%s in %s mode", settings.app_name, settings.app_version, settings.environment)
    init_db(settings.resolved_db_path)

    coordinator: Optional[ChangeCoordinator] = None
    debouncer: Optional[ChangeDebouncer] = None
    watcher: Optional[FileSystemWatcher] = None

    if settings.watcher_enabled and settings.environment != "testing":
        try:
            db = DatabaseConnectionManager(db_path=settings.resolved_db_path)
            vector_store = ChromaVectorStore(persist_dir=settings.vectors_dir)
            resolved_model = settings.resolved_embedding_model
            config = EmbeddingConfig(
                model_id=resolved_model,
                dimension=settings.embedding_dimension,
                batch_size=settings.embedding_batch_size,
                device=settings.embedding_device,
                precision=settings.embedding_precision,
                local_files_only=(resolved_model != settings.embedding_model_id),
            )
            embedder = EmbeddingGemmaEmbedder(config=config)
            semantic_pipeline = SemanticPipeline(db=db, embedder=embedder, vector_store=vector_store)
            indexing_service = IndexingService(db=db, semantic_pipeline=semantic_pipeline)

            coordinator = ChangeCoordinator(indexing_service=indexing_service)
            debouncer = ChangeDebouncer(on_event=coordinator.enqueue, debounce_ms=settings.watcher_debounce_ms)
            watcher = FileSystemWatcher(debouncer=debouncer)

            coordinator.start()
            watcher.start()

            # Schedule watches for all active registered folders
            with db.connection() as conn:
                active_folders = FolderRepository.list_active(conn)
            for folder in active_folders:
                if folder.id is not None:
                    watcher.add_folder(folder.id, folder.path)

            app.state.file_watcher = watcher
            app.state.change_debouncer = debouncer
            app.state.change_coordinator = coordinator
            app.state.indexing_service = indexing_service

            # Run non-blocking startup reconciliation in a background thread
            reconciler = StartupReconciler(db=db, indexing_service=indexing_service)
            reconcile_thread = Thread(
                target=reconciler.reconcile_all_active_folders,
                kwargs={"generate_embeddings": True},
                daemon=True,
                name="StartupReconcilerWorker",
            )
            reconcile_thread.start()
            logger.info("Incremental file watcher and startup reconciler launched successfully")

        except Exception as exc:
            logger.error("Failed to start filesystem monitoring subsystem: %s", exc, exc_info=True)

    yield

    logger.info("Shutting down %s", settings.app_name)
    if watcher:
        try:
            watcher.stop()
        except Exception as exc:
            logger.warning("Error stopping filesystem watcher: %s", exc)
    if debouncer:
        try:
            debouncer.stop()
        except Exception as exc:
            logger.warning("Error stopping event debouncer: %s", exc)
    if coordinator:
        try:
            coordinator.stop()
        except Exception as exc:
            logger.warning("Error stopping change coordinator: %s", exc)


def create_app() -> FastAPI:
    """FastAPI application factory."""
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Local-first, AI-powered multifile search backend API",
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        lifespan=lifespan,
    )

    # Configure CORS for local frontend communication
    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # Global Exception Handlers
    @app.exception_handler(OmniSearchException)
    async def handle_omnisearch_exception(request: Request, exc: OmniSearchException) -> JSONResponse:
        logger.warning("Application exception on %s %s: %s (code: %s)", request.method, request.url.path, exc.message, exc.code)
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.__class__.__name__,
                "detail": exc.message,
                "code": exc.code,
                "status_code": exc.status_code,
                "details": exc.details,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        logger.warning("Validation error on %s %s: %s", request.method, request.url.path, exc)
        return JSONResponse(
            status_code=422,
            content={
                "error": "RequestValidationError",
                "detail": str(exc),
                "code": "VALIDATION_ERROR",
                "status_code": 422,
                "details": {"errors": exc.errors()},
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": "HTTPException",
                "detail": str(exc.detail),
                "code": f"HTTP_{exc.status_code}",
                "status_code": exc.status_code,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

    @app.exception_handler(Exception)
    async def handle_general_exception(request: Request, exc: Exception) -> JSONResponse:
        logger.error("Unhandled server exception on %s %s: %s", request.method, request.url.path, exc, exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "error": "InternalServerError",
                "detail": "An unexpected internal server error occurred.",
                "code": "INTERNAL_SERVER_ERROR",
                "status_code": 500,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

    # Mount API v1 router
    app.include_router(api_router, prefix="/api/v1")

    return app


app = create_app()

if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
