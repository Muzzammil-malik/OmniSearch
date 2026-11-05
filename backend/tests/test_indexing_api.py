"""Integration tests for Indexing API endpoints and IndexingService."""

from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.api.v1.endpoints.folders import get_folder_service, get_indexing_service
from app.database.connection import DatabaseConnectionManager
from app.database.migrations import apply_migrations
from app.database.repositories.jobs import JobRepository
from app.main import create_app
from app.schemas.processing import IndexJobStatus
from app.services.folder_service import FolderService
from app.services.indexer import IndexingService


@pytest.fixture
def indexing_env(tmp_path: Path):
    """Setup isolated test environment for indexing API operations."""
    db_file = tmp_path / "test_indexing.db"
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


def test_start_indexing_specific_folder(indexing_env):
    """Verify POST /api/v1/indexing/start with folder_id indexes the requested folder."""
    client, folder_service, _, _, tmp_path = indexing_env
    folder_a = tmp_path / "folder_a"
    folder_a.mkdir()
    (folder_a / "file1.txt").write_text("Keyword search content in file 1", encoding="utf-8")

    fld = folder_service.register_folder(str(folder_a))

    response = client.post(
        "/api/v1/indexing/start",
        json={"folder_id": fld.id, "generate_embeddings": False},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["total_files"] == 1
    assert data["successful_files"] == 1


def test_start_indexing_all_folders(indexing_env):
    """Verify POST /api/v1/indexing/start without folder_id indexes all active folders."""
    client, folder_service, _, _, tmp_path = indexing_env
    dir1 = tmp_path / "dir1"
    dir1.mkdir()
    (dir1 / "alpha.txt").write_text("Alpha document content", encoding="utf-8")

    dir2 = tmp_path / "dir2"
    dir2.mkdir()
    (dir2 / "beta.txt").write_text("Beta document content", encoding="utf-8")

    folder_service.register_folder(str(dir1))
    folder_service.register_folder(str(dir2))

    response = client.post(
        "/api/v1/indexing/start",
        json={"generate_embeddings": False},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"


def test_indexing_status_and_recent_jobs(indexing_env):
    """Verify GET /api/v1/indexing/status and GET /api/v1/indexing/jobs."""
    client, folder_service, _, _, tmp_path = indexing_env
    test_dir = tmp_path / "jobs_test"
    test_dir.mkdir()
    (test_dir / "doc.txt").write_text("Indexing history document", encoding="utf-8")

    fld = folder_service.register_folder(str(test_dir))
    client.post("/api/v1/indexing/start", json={"folder_id": fld.id, "generate_embeddings": False})

    # Status check
    status_resp = client.get("/api/v1/indexing/status")
    assert status_resp.status_code == 200
    status_data = status_resp.json()
    assert "is_indexing" in status_data
    assert isinstance(status_data["recent_jobs"], list)
    assert len(status_data["recent_jobs"]) >= 1

    # Jobs list check
    jobs_resp = client.get("/api/v1/indexing/jobs?limit=5")
    assert jobs_resp.status_code == 200
    jobs_data = jobs_resp.json()
    assert len(jobs_data) >= 1
    assert jobs_data[0]["status"] == "completed"


def test_get_indexing_job_by_id(indexing_env):
    """Verify GET /api/v1/indexing/jobs/{job_id} retrieves job details or 404."""
    client, folder_service, _, _, tmp_path = indexing_env
    test_dir = tmp_path / "single_job"
    test_dir.mkdir()
    (test_dir / "doc.txt").write_text("Single job document", encoding="utf-8")

    fld = folder_service.register_folder(str(test_dir))
    start_resp = client.post("/api/v1/indexing/start", json={"folder_id": fld.id, "generate_embeddings": False})
    job_id = start_resp.json()["id"]

    get_resp = client.get(f"/api/v1/indexing/jobs/{job_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == job_id

    missing_resp = client.get("/api/v1/indexing/jobs/99999")
    assert missing_resp.status_code == 404
    assert missing_resp.json()["code"] == "JOB_NOT_FOUND"


def test_indexing_stats_endpoint(indexing_env):
    """Verify GET /api/v1/indexing/stats returns aggregated metrics across index."""
    client, folder_service, _, _, tmp_path = indexing_env
    test_dir = tmp_path / "stats_folder"
    test_dir.mkdir()
    (test_dir / "file_a.txt").write_text("Statistics test document content", encoding="utf-8")

    fld = folder_service.register_folder(str(test_dir))
    client.post("/api/v1/indexing/start", json={"folder_id": fld.id, "generate_embeddings": False})

    stats_resp = client.get("/api/v1/indexing/stats")
    assert stats_resp.status_code == 200
    stats = stats_resp.json()
    assert stats["total_folders"] >= 1
    assert stats["total_files"] >= 1
    assert stats["successful_files"] >= 1
    assert stats["total_chunks"] >= 1


def test_indexing_conflict_when_running(indexing_env):
    """Verify trigger indexing returns 409 Conflict when an indexing job is already in progress."""
    client, _, _, db, tmp_path = indexing_env
    test_dir = tmp_path / "conflict_dir"
    test_dir.mkdir()

    # Manually create a job with RUNNING status in the database
    with db.transaction() as conn:
        running_id = JobRepository.create(conn, total_files=10)

    # Attempt to trigger another job
    response = client.post(
        "/api/v1/indexing/start",
        json={"folder_path": str(test_dir), "generate_embeddings": False},
    )
    assert response.status_code == 409
    data = response.json()
    assert data["code"] == "INDEXING_IN_PROGRESS"

    # Clean up running job
    with db.transaction() as conn:
        JobRepository.finish(conn, running_id, IndexJobStatus.COMPLETED)
