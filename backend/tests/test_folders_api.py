"""Integration tests for Folder management API endpoints and FolderService."""

from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.api.v1.endpoints.folders import get_folder_service, get_indexing_service
from app.database.connection import DatabaseConnectionManager
from app.database.migrations import apply_migrations
from app.database.repositories.chunks import ChunkRepository
from app.database.repositories.files import FileRepository
from app.database.repositories.folders import FolderRepository
from app.main import create_app
from app.schemas.processing import DocumentChunk, FileRecord
from app.services.folder_service import FolderService
from app.services.indexer import IndexingService


@pytest.fixture
def folder_env(tmp_path: Path):
    """Setup isolated test database and services for folder management."""
    db_file = tmp_path / "test_folders.db"
    db = DatabaseConnectionManager(db_path=db_file)
    with db.connection() as conn:
        apply_migrations(conn)

    folder_service = FolderService(db=db)
    indexing_service = IndexingService(db=db)

    app = create_app()
    app.dependency_overrides[get_folder_service] = lambda: folder_service
    app.dependency_overrides[get_indexing_service] = lambda: indexing_service
    client = TestClient(app)

    return client, folder_service, indexing_service, db, tmp_path


def test_folder_registration_valid(folder_env):
    """Verify registering a valid local directory succeeds with 201 Created."""
    client, _, _, _, tmp_path = folder_env
    target_dir = tmp_path / "documents"
    target_dir.mkdir()

    response = client.post("/api/v1/folders", json={"path": str(target_dir), "enabled": True})
    assert response.status_code == 201
    data = response.json()
    assert data["id"] > 0
    assert Path(data["path"]) == target_dir.resolve()
    assert data["enabled"] is True
    assert data["file_count"] == 0


def test_folder_registration_nonexistent(folder_env):
    """Verify registering a nonexistent directory returns 400 with INVALID_FOLDER_PATH."""
    client, _, _, _, tmp_path = folder_env
    missing_dir = tmp_path / "does_not_exist"

    response = client.post("/api/v1/folders", json={"path": str(missing_dir)})
    assert response.status_code == 400
    data = response.json()
    assert data["code"] == "INVALID_FOLDER_PATH"
    assert "Directory does not exist" in data["detail"]


def test_folder_registration_file_instead_of_dir(folder_env):
    """Verify registering a regular file instead of a directory returns 400."""
    client, _, _, _, tmp_path = folder_env
    regular_file = tmp_path / "note.txt"
    regular_file.write_text("Hello world", encoding="utf-8")

    response = client.post("/api/v1/folders", json={"path": str(regular_file)})
    assert response.status_code == 400
    data = response.json()
    assert data["code"] == "INVALID_FOLDER_PATH"
    assert "is a file" in data["detail"]


def test_folder_registration_duplicate(folder_env):
    """Verify registering the same directory path twice returns 409 Conflict."""
    client, _, _, _, tmp_path = folder_env
    target_dir = tmp_path / "shared"
    target_dir.mkdir()

    # First registration
    resp1 = client.post("/api/v1/folders", json={"path": str(target_dir)})
    assert resp1.status_code == 201

    # Second registration
    resp2 = client.post("/api/v1/folders", json={"path": str(target_dir)})
    assert resp2.status_code == 409
    data = resp2.json()
    assert data["code"] == "DUPLICATE_FOLDER"


def test_list_folders_with_stats(folder_env):
    """Verify GET /api/v1/folders returns all registered folders with aggregated counts."""
    client, _, _, db, tmp_path = folder_env
    dir_a = tmp_path / "dir_a"
    dir_a.mkdir()

    # Register folder and seed files/chunks
    with db.transaction() as conn:
        fld = FolderRepository.get_or_create(conn, str(dir_a))
        fid = FileRepository.upsert(
            conn,
            FileRecord(
                folder_id=fld.id,
                path=str(dir_a / "doc1.txt"),
                filename="doc1.txt",
                extension=".txt",
                file_type="text",
                size_bytes=1024,
                modified_at="2026-11-05T00:00:00Z",
                status="success",
            ),
        )
        ChunkRepository.insert_chunks(
            conn,
            fid,
            [
                DocumentChunk(chunk_index=0, content="Content 1", token_count=10),
                DocumentChunk(chunk_index=1, content="Content 2", token_count=12),
            ],
        )

    response = client.get("/api/v1/folders")
    assert response.status_code == 200
    data = response.json()
    assert data["total_folders"] >= 1
    found = next((f for f in data["folders"] if f["id"] == fld.id), None)
    assert found is not None
    assert found["file_count"] == 1
    assert found["total_size_bytes"] == 1024
    assert found["chunk_count"] == 2


def test_get_folder_by_id(folder_env):
    """Verify GET /api/v1/folders/{id} returns folder details or 404."""
    client, _, _, _, tmp_path = folder_env
    target_dir = tmp_path / "inspect"
    target_dir.mkdir()

    create_resp = client.post("/api/v1/folders", json={"path": str(target_dir)})
    folder_id = create_resp.json()["id"]

    # Valid folder ID
    get_resp = client.get(f"/api/v1/folders/{folder_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == folder_id

    # Nonexistent folder ID
    missing_resp = client.get("/api/v1/folders/99999")
    assert missing_resp.status_code == 404
    assert missing_resp.json()["code"] == "FOLDER_NOT_FOUND"


def test_update_folder_toggle(folder_env):
    """Verify PATCH /api/v1/folders/{id} updates enabled state."""
    client, _, _, _, tmp_path = folder_env
    target_dir = tmp_path / "toggleable"
    target_dir.mkdir()

    create_resp = client.post("/api/v1/folders", json={"path": str(target_dir), "enabled": True})
    folder_id = create_resp.json()["id"]

    # Disable folder
    patch_resp = client.patch(f"/api/v1/folders/{folder_id}", json={"enabled": False})
    assert patch_resp.status_code == 200
    assert patch_resp.json()["enabled"] is False

    # Re-enable folder
    patch_resp2 = client.patch(f"/api/v1/folders/{folder_id}", json={"enabled": True})
    assert patch_resp2.status_code == 200
    assert patch_resp2.json()["enabled"] is True


def test_delete_folder_cascade(folder_env):
    """Verify DELETE /api/v1/folders/{id} removes folder and cascade-deletes files/chunks."""
    client, _, _, db, tmp_path = folder_env
    target_dir = tmp_path / "to_delete"
    target_dir.mkdir()

    create_resp = client.post("/api/v1/folders", json={"path": str(target_dir)})
    folder_id = create_resp.json()["id"]

    # Seed file and chunk
    with db.transaction() as conn:
        fid = FileRepository.upsert(
            conn,
            FileRecord(
                folder_id=folder_id,
                path=str(target_dir / "del.txt"),
                filename="del.txt",
                extension=".txt",
                file_type="text",
                modified_at="2026-11-05T00:00:00Z",
                status="success",
            ),
        )
        ChunkRepository.insert_chunks(
            conn, fid, [DocumentChunk(chunk_index=0, content="del content", token_count=5)]
        )

    # Delete folder
    del_resp = client.delete(f"/api/v1/folders/{folder_id}")
    assert del_resp.status_code == 200
    assert del_resp.json()["success"] is True

    # Confirm folder, files, and chunks are gone
    with db.connection() as conn:
        assert FolderRepository.get_by_id(conn, folder_id) is None
        assert FileRepository.get_by_id(conn, fid) is None
        assert ChunkRepository.count_by_file_id(conn, fid) == 0


def test_index_specific_folder_endpoint(folder_env):
    """Verify POST /api/v1/folders/{id}/index triggers indexing for the given folder."""
    client, _, _, _, tmp_path = folder_env
    target_dir = tmp_path / "indexed_folder"
    target_dir.mkdir()
    (target_dir / "sample.txt").write_text("FastAPI application services in OmniSearch", encoding="utf-8")

    create_resp = client.post("/api/v1/folders", json={"path": str(target_dir)})
    folder_id = create_resp.json()["id"]

    index_resp = client.post(f"/api/v1/folders/{folder_id}/index?generate_embeddings=false")
    assert index_resp.status_code == 200
    job_data = index_resp.json()
    assert job_data["status"] == "completed"
    assert job_data["total_files"] == 1
    assert job_data["successful_files"] == 1

