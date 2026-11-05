"""Integration tests for System diagnostics API endpoints and SystemService."""

from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.api.v1.endpoints.system import get_system_service
from app.database.connection import DatabaseConnectionManager
from app.database.migrations import apply_migrations
from app.embeddings.model_manager import EmbeddingModelManager
from app.main import create_app
from app.services.system_service import SystemService
from app.vector_store.chroma import ChromaVectorStore


@pytest.fixture
def system_env(tmp_path: Path):
    """Setup isolated test database and SystemService."""
    db_file = tmp_path / "system_test.db"
    db = DatabaseConnectionManager(db_path=db_file)
    with db.connection() as conn:
        apply_migrations(conn)

    vector_store = ChromaVectorStore(
        persist_dir=tmp_path / "vectors", collection_name="test_system"
    )

    system_service = SystemService(db=db, vector_store=vector_store)

    app = create_app()
    app.dependency_overrides[get_system_service] = lambda: system_service
    client = TestClient(app)

    return client, system_service


def test_system_status_endpoint(system_env):
    """Verify GET /api/v1/system/status returns diagnostic details across all subsystems."""
    client, _ = system_env
    response = client.get("/api/v1/system/status")
    assert response.status_code == 200
    data = response.json()

    assert data["status"] in ("healthy", "degraded")
    assert "database" in data
    assert data["database"]["status"] == "healthy"
    assert data["database"]["wal_mode"] is True

    assert "vector_store" in data
    assert data["vector_store"]["status"] in ("available", "empty")

    assert "embedding_model" in data
    assert "model_id" in data["embedding_model"]
    assert "is_loaded" in data["embedding_model"]


def test_system_status_model_not_loaded_at_startup(system_env):
    """Verify checking system status does NOT eagerly load the embedding model into RAM."""
    client, _ = system_env
    # Release model if previously loaded in another test
    manager = EmbeddingModelManager.get_instance()
    manager.unload()

    assert manager.is_loaded is False

    response = client.get("/api/v1/system/status")
    assert response.status_code == 200

    # Model MUST remain unloaded after status check
    assert manager.is_loaded is False


def test_system_stats_endpoint(system_env):
    """Verify GET /api/v1/system/stats returns content metrics."""
    client, _ = system_env
    response = client.get("/api/v1/system/stats")
    assert response.status_code == 200
    data = response.json()
    assert "total_folders" in data
    assert "total_files" in data
    assert "total_chunks" in data
