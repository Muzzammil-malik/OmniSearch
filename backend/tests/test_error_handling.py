"""Integration tests verifying consistent error handling and absence of traceback leaks."""

from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.core.exceptions import OmniSearchException
from app.main import create_app


@pytest.fixture
def test_client():
    """Setup test client with route that forces an unhandled exception."""
    app = create_app()

    @app.get("/api/v1/test-unhandled-error")
    def trigger_unhandled():
        raise RuntimeError("Sensitive internal database connection password leaked!")

    @app.get("/api/v1/test-omnisearch-error")
    def trigger_omnisearch_error():
        raise OmniSearchException("Custom domain error occurred", code="CUSTOM_CODE", status_code=400)

    return TestClient(app, raise_server_exceptions=False)


def test_validation_error_422(test_client):
    """Verify request validation error returns standardized 422 JSON response."""
    # POST to /api/v1/folders with missing required field 'path'
    response = test_client.post("/api/v1/folders", json={"enabled": True})
    assert response.status_code == 422
    data = response.json()
    assert data["code"] == "VALIDATION_ERROR"
    assert data["status_code"] == 422
    assert "detail" in data
    assert "timestamp" in data


def test_not_found_404(test_client):
    """Verify nonexistent URL route returns standardized 404 response."""
    response = test_client.get("/api/v1/nonexistent-endpoint-abc")
    assert response.status_code == 404
    data = response.json()
    assert data["status_code"] == 404
    assert "timestamp" in data


def test_omnisearch_custom_exception(test_client):
    """Verify OmniSearchException returns structured domain error."""
    response = test_client.get("/api/v1/test-omnisearch-error")
    assert response.status_code == 400
    data = response.json()
    assert data["error"] == "OmniSearchException"
    assert data["detail"] == "Custom domain error occurred"
    assert data["code"] == "CUSTOM_CODE"
    assert data["status_code"] == 400


def test_unhandled_exception_no_traceback_leak(test_client):
    """Verify unhandled 500 error does NOT leak internal exception strings or raw tracebacks."""
    response = test_client.get("/api/v1/test-unhandled-error")
    assert response.status_code == 500
    data = response.json()
    assert data["status_code"] == 500
    assert data["code"] == "INTERNAL_SERVER_ERROR"
    assert "An unexpected internal server error occurred" in data["detail"]
    # Sensitive error message MUST NOT be leaked to the client
    assert "Sensitive internal database connection password" not in str(data)
    assert "Traceback" not in str(data)
