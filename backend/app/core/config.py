"""Centralized application configuration using Pydantic Settings."""

import os
from functools import lru_cache
from pathlib import Path
from typing import List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def get_default_local_appdata() -> Path:
    """Return platform-standard local application data directory."""
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "OmniSearch"
    return Path.home() / "AppData" / "Local" / "OmniSearch"


def get_default_roaming_appdata() -> Path:
    """Return platform-standard roaming application data directory."""
    roaming_data = os.environ.get("APPDATA")
    if roaming_data:
        return Path(roaming_data) / "OmniSearch"
    return Path.home() / "AppData" / "Roaming" / "OmniSearch"


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env files."""

    app_name: str = Field(default="OmniSearch Backend", description="Display name of the application")
    app_version: str = Field(default="0.1.0", description="Semantic version string")
    environment: str = Field(default="development", description="Runtime environment: development, testing, production")
    debug: bool = Field(default=True, description="Enable debug mode")

    # Network configuration - local-first desktop application binds to 127.0.0.1
    host: str = Field(default="127.0.0.1", description="Host address for local server binding")
    port: int = Field(default=8000, description="Port number for local server binding")

    # Security & CORS
    cors_origins: List[str] = Field(
        default=["http://localhost:3000", "http://127.0.0.1:3000"],
        description="Allowed CORS origin list for local frontend access",
    )

    # Logging
    log_level: str = Field(default="INFO", description="Standard logging level")

    # Storage Locations (Phase 3)
    data_dir: Path = Field(
        default_factory=lambda: get_default_local_appdata() / "data",
        description="Directory for local database and persistent indices",
    )
    models_dir: Path = Field(
        default_factory=lambda: get_default_local_appdata() / "models",
        description="Directory for local AI and embedding model weights",
    )
    logs_dir: Path = Field(
        default_factory=lambda: get_default_local_appdata() / "logs",
        description="Directory for persistent application log files",
    )
    config_dir: Path = Field(
        default_factory=lambda: get_default_roaming_appdata(),
        description="Directory for user roaming configuration and settings",
    )

    # Database Path (defaults to data_dir / omnisearch.db, configurable for tests)
    db_path: Optional[Path] = Field(
        default=None,
        description="Explicit database file path. If None, resolves to data_dir / omnisearch.db",
    )

    # Chunking Configuration (Phase 3)
    chunk_target_tokens: int = Field(
        default=500,
        description="Target size for document chunks in tokens (recommended: 450-600)",
    )
    chunk_overlap_tokens: int = Field(
        default=80,
        description="Token overlap between consecutive chunks for semantic context continuity",
    )

    # Vector Storage and Semantic Embeddings (Phase 5)
    vectors_dir: Path = Field(
        default_factory=lambda: get_default_local_appdata() / "vectors",
        description="Directory for ChromaDB local persistent vector storage",
    )
    embedding_model_id: str = Field(
        default="google/embeddinggemma-2",
        description="HuggingFace model identifier for Google EmbeddingGemma 2",
    )
    embedding_dimension: int = Field(
        default=768,
        description="Target vector dimension (EmbeddingGemma 2 default: 768; supports MRL: 512, 256, 128)",
    )
    embedding_batch_size: int = Field(
        default=16,
        description="Batch size for generating document chunk embeddings on CPU",
    )
    embedding_fetch_pool_size: int = Field(
        default=128,
        description="Number of candidate chunks fetched from SQLite per embedding sync cycle for length-aware coalesced batching",
    )
    embedding_device: str = Field(
        default="cpu",
        description="Device for embedding model inference ('cpu' or 'cuda' if supported)",
    )
    embedding_precision: str = Field(
        default="float32",
        description="Floating-point precision for embedding inference ('float32' or 'bfloat16')",
    )

    # OCR Configuration (Phase 9)
    ocr_enabled: bool = Field(
        default=True,
        description="Enable local OCR fallback for scanned and image-only PDF documents",
    )
    ocr_tessdata_dir: Optional[Path] = Field(
        default=None,
        description="Custom directory containing tessdata language models (e.g. eng.traineddata)",
    )

    # File System Watcher & Incremental Indexing (Phase 9)
    watcher_enabled: bool = Field(
        default=True,
        description="Enable automatic filesystem monitoring for registered active folders",
    )
    watcher_debounce_ms: int = Field(
        default=800,
        description="Debounce window in milliseconds for coalescing rapid filesystem events",
    )

    @property
    def resolved_ocr_tessdata_dir(self) -> Path:
        """Resolve directory containing Tesseract language data files."""
        if self.ocr_tessdata_dir is not None:
            return self.ocr_tessdata_dir
        # Check repo workspace data directory first if present
        repo_tessdata = Path(__file__).resolve().parent.parent.parent / "data" / "ocr" / "tessdata"
        if repo_tessdata.exists() and (repo_tessdata / "eng.traineddata").exists():
            return repo_tessdata
        return self.data_dir / "ocr" / "tessdata"

    @property
    def resolved_db_path(self) -> Path:
        """Resolve database path, ensuring data directory exists."""
        if self.db_path is not None:
            return self.db_path
        return self.data_dir / "omnisearch.db"

    @property
    def resolved_embedding_model(self) -> str:
        """Resolve model identifier to local directory if present, else configured model ID."""
        local_model_dir = self.models_dir / "embeddinggemma-2"
        if local_model_dir.exists() and (local_model_dir / "model.safetensors").exists():
            return str(local_model_dir)
        return self.embedding_model_id

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings instance."""
    return Settings()

