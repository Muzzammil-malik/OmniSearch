"""Regression tests for semantic embedding error reporting, endpoint schemas, and async triggers."""

from pathlib import Path
from unittest.mock import MagicMock
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
def test_env(tmp_path: Path):
    """Setup isolated test database, mock semantic pipeline, and API test client."""
    db_file = tmp_path / "test_indexing_fixes.db"
    db = DatabaseConnectionManager(db_path=db_file)
    with db.connection() as conn:
        apply_migrations(conn)

    mock_semantic_pipeline = MagicMock()
    mock_semantic_pipeline.sync_embeddings.return_value = 5

    folder_service = FolderService(db=db)
    indexing_service = IndexingService(db=db, semantic_pipeline=mock_semantic_pipeline)

    app = create_app()
    app.dependency_overrides[get_folder_service] = lambda: folder_service
    app.dependency_overrides[get_indexing_service] = lambda: indexing_service
    client = TestClient(app)

    return client, indexing_service, mock_semantic_pipeline, db, tmp_path


def test_embedding_failure_records_error_and_status(test_env):
    """Verify that when sync_embeddings raises an exception, the job is marked COMPLETED_WITH_ERRORS."""
    _, indexing_service, mock_semantic_pipeline, db, tmp_path = test_env
    folder = tmp_path / "sample_folder"
    folder.mkdir()
    (folder / "file1.txt").write_text("Hello world content", encoding="utf-8")

    # Configure semantic pipeline to fail
    mock_semantic_pipeline.sync_embeddings.side_effect = RuntimeError("Embedding model OOM or device failure")

    job = indexing_service.index_folder(
        folder_path=folder,
        reconcile_deleted=True,
        force_reindex=False,
        generate_embeddings=True,
    )

    assert job.status == IndexJobStatus.COMPLETED_WITH_ERRORS
    assert job.error_message is not None
    assert "Embedding generation failed: Embedding model OOM or device failure" in job.error_message

    # Verify database persistence
    with db.connection() as conn:
        persisted_job = JobRepository.get_by_id(conn, job.id)
        assert persisted_job is not None
        assert persisted_job.status == IndexJobStatus.COMPLETED_WITH_ERRORS
        assert persisted_job.error_message == job.error_message


def test_folder_index_endpoint_accepts_json_body(test_env):
    """Verify POST /folders/{id}/index parses and respects JSON request body."""
    client, indexing_service, mock_semantic_pipeline, db, tmp_path = test_env
    folder = tmp_path / "json_folder"
    folder.mkdir()
    (folder / "test.txt").write_text("Testing folder indexing with JSON body", encoding="utf-8")

    # Register folder
    create_resp = client.post("/api/v1/folders", json={"path": str(folder)})
    assert create_resp.status_code == 201
    folder_id = create_resp.json()["id"]

    # Post with JSON body
    index_resp = client.post(
        f"/api/v1/folders/{folder_id}/index",
        json={
            "force_reindex": False,
            "reconcile_deleted": True,
            "generate_embeddings": True,
            "background": False,
        },
    )
    assert index_resp.status_code == 200
    job_data = index_resp.json()
    assert job_data["status"] == "completed"
    assert job_data["successful_files"] == 1
    mock_semantic_pipeline.sync_embeddings.assert_called()


def test_generate_embeddings_false_skips_embedding(test_env):
    """Verify that generate_embeddings=False bypasses sync_embeddings call."""
    client, indexing_service, mock_semantic_pipeline, db, tmp_path = test_env
    folder = tmp_path / "no_embed_folder"
    folder.mkdir()
    (folder / "doc.txt").write_text("Skip embedding content", encoding="utf-8")

    create_resp = client.post("/api/v1/folders", json={"path": str(folder)})
    folder_id = create_resp.json()["id"]

    # Trigger with generate_embeddings = False
    index_resp = client.post(
        f"/api/v1/folders/{folder_id}/index",
        json={"generate_embeddings": False},
    )
    assert index_resp.status_code == 200
    assert index_resp.json()["status"] == "completed"
    mock_semantic_pipeline.sync_embeddings.assert_not_called()


def test_background_indexing_execution(test_env):
    """Verify triggering indexing with background=True returns immediately."""
    client, indexing_service, mock_semantic_pipeline, db, tmp_path = test_env
    folder = tmp_path / "bg_folder"
    folder.mkdir()
    (folder / "bg_file.txt").write_text("Background indexing file content", encoding="utf-8")

    create_resp = client.post("/api/v1/folders", json={"path": str(folder)})
    folder_id = create_resp.json()["id"]

    index_resp = client.post(
        f"/api/v1/folders/{folder_id}/index",
        json={"background": True, "generate_embeddings": True},
    )
    assert index_resp.status_code == 200
    job_data = index_resp.json()
    assert job_data["id"] > 0
    assert job_data["status"] in ("running", "completed")

