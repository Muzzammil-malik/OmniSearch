"""OmniSearch backend application entry point."""

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import AsyncGenerator
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
from app.database.initialization import init_db

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application startup and shutdown lifecycle events."""
    settings = get_settings()
    setup_logging(settings.log_level)
    logger.info("Starting %s v%s in %s mode", settings.app_name, settings.app_version, settings.environment)
    init_db(settings.resolved_db_path)
    yield
    logger.info("Shutting down %s", settings.app_name)


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
