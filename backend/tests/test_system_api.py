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
        from app.database.repositories.folders import FolderRepository
        FolderRepository.get_or_create(conn, str(tmp_path))

    vector_store = ChromaVectorStore(
        persist_dir=tmp_path / "vectors", collection_name="test_system"
    )

    system_service = SystemService(db=db, vector_store=vector_store)

    app = create_app()
    app.dependency_overrides[get_system_service] = lambda: system_service
    app.dependency_overrides[DatabaseConnectionManager] = lambda: db
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


def test_pick_folder_native_selected(system_env, tmp_path):
    """Verify POST /api/v1/system/pick-folder returns selected path when user selects directory."""
    from unittest.mock import patch, MagicMock

    client, _ = system_env
    mock_dir = str(tmp_path / "selected_documents")

    with patch("tkinter.Tk") as mock_tk_cls:
        mock_root = MagicMock()
        mock_tk_cls.return_value = mock_root
        with patch("tkinter.filedialog.askdirectory", return_value=mock_dir):
            response = client.post("/api/v1/system/pick-folder")
            assert response.status_code == 200
            data = response.json()
            assert data["canceled"] is False
            assert Path(data["path"]) == Path(mock_dir).resolve()


def test_pick_folder_native_canceled(system_env):
    """Verify POST /api/v1/system/pick-folder returns canceled: true when user dismisses dialog."""
    from unittest.mock import patch, MagicMock

    client, _ = system_env

    with patch("tkinter.Tk") as mock_tk_cls:
        mock_root = MagicMock()
        mock_tk_cls.return_value = mock_root
        with patch("tkinter.filedialog.askdirectory", return_value=""):
            response = client.post("/api/v1/system/pick-folder")
            assert response.status_code == 200
            data = response.json()
            assert data["canceled"] is True
            assert data["path"] is None


def test_file_content_endpoint(system_env, tmp_path):
    """Verify GET /api/v1/system/file-content serves existing files, blocks unauthorized paths, and returns 404 for missing."""
    client, _ = system_env
    test_file = tmp_path / "sample.png"
    test_file.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + b"\x00" * 50)

    # 1. Existing file returns 200 with appropriate image MIME type and inline header
    res = client.get(f"/api/v1/system/file-content?path={test_file}")
    assert res.status_code == 200
    assert res.headers["content-type"] == "image/png"
    assert "inline" in res.headers.get("content-disposition", "")
    assert res.headers.get("accept-ranges") == "bytes"

    # 2. Missing file inside library returns 404
    missing_file = tmp_path / "nonexistent.png"
    res_missing = client.get(f"/api/v1/system/file-content?path={missing_file}")
    assert res_missing.status_code == 404

    # 3. Unauthorized file outside library returns 403 Forbidden
    outside_file = tmp_path.parent / "unauthorized.txt"
    outside_file.write_text("secret", encoding="utf-8")
    res_unauth = client.get(f"/api/v1/system/file-content?path={outside_file}")
    assert res_unauth.status_code == 403

    # 4. Range request support for media streaming
    res_range = client.get(
        f"/api/v1/system/file-content?path={test_file}",
        headers={"Range": "bytes=0-7"},
    )
    assert res_range.status_code == 206
    assert len(res_range.content) == 8


def test_open_and_reveal_file_endpoints(system_env, tmp_path):
    """Verify POST /api/v1/system/open-file and /system/reveal-file endpoints validate path existence."""
    client, _ = system_env
    test_file = tmp_path / "document.pdf"
    test_file.write_bytes(b"%PDF-1.4 mock")

    # Missing file returns error
    res_bad = client.post("/api/v1/system/open-file", json={"path": str(tmp_path / "fake.pdf")})
    assert res_bad.status_code == 200
    assert res_bad.json()["success"] is False
    assert "File no longer exists" in res_bad.json()["error"]

    # Existing file with mocked OS launcher succeeds
    from unittest.mock import patch
    with patch("os.startfile", create=True):
        res_open = client.post("/api/v1/system/open-file", json={"path": str(test_file)})
        assert res_open.status_code == 200
        assert res_open.json()["success"] is True

    with patch("subprocess.run"):
        res_reveal = client.post("/api/v1/system/reveal-file", json={"path": str(test_file)})
        assert res_reveal.status_code == 200
        assert res_reveal.json()["success"] is True


