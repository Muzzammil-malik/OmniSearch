"""Pytest fixtures for backend tests."""

import os
from pathlib import Path

_test_dir = Path(__file__).resolve().parent / ".test_data"
_test_dir.mkdir(exist_ok=True)
(_test_dir / "data").mkdir(exist_ok=True)
(_test_dir / "vectors").mkdir(exist_ok=True)

os.environ["ENVIRONMENT"] = "testing"
os.environ["WATCHER_ENABLED"] = "false"
os.environ["DATA_DIR"] = str((_test_dir / "data").resolve())
os.environ["VECTORS_DIR"] = str((_test_dir / "vectors").resolve())
os.environ["DB_PATH"] = str((_test_dir / "data" / "omnisearch_test.db").resolve())
os.environ["OCR_TESSDATA_DIR"] = str((Path(__file__).resolve().parent.parent / "data" / "ocr" / "tessdata").resolve())

from app.core.config import get_settings
get_settings.cache_clear()

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from app.main import create_app


@pytest.fixture
def app():
    """Create a fresh FastAPI test application instance."""
    return create_app()


@pytest_asyncio.fixture
async def async_client(app):
    """Provide an asynchronous HTTP client bound to the FastAPI application."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
