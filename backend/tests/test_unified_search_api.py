"""Integration tests for Unified Search API endpoints and SearchService."""

from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.api.v1.endpoints.search import (
    get_hybrid_search_engine,
    get_search_engine,
    get_search_service,
    get_semantic_search_engine,
)
from app.database.connection import DatabaseConnectionManager
from app.database.migrations import apply_migrations
from app.database.repositories.chunks import ChunkRepository
from app.database.repositories.files import FileRepository
from app.database.repositories.folders import FolderRepository
from app.embeddings.test_embedder import DeterministicTestEmbedder
from app.main import create_app
from app.schemas.processing import DocumentChunk, FileRecord
from app.schemas.search import (
    SearchModeEnum,
    UnifiedSearchQuery,
    UnifiedSearchResponse,
)
from app.search.hybrid_search import HybridSearchEngine
from app.search.keyword_search import KeywordSearchEngine
from app.search.semantic_search import SemanticSearchEngine
from app.services.search_service import SearchService
from app.vector_store.chroma import ChromaVectorStore


@pytest.fixture
def search_service_env(tmp_path: Path):
    """Setup SQLite FTS5 database, ChromaVectorStore, and SearchService."""
    db_file = tmp_path / "unified_search.db"
    db = DatabaseConnectionManager(db_path=db_file)
    with db.connection() as conn:
        apply_migrations(conn)

    vector_store = ChromaVectorStore(
        persist_dir=tmp_path / "vectors", collection_name="test_unified_search"
    )
    embedder = DeterministicTestEmbedder(dimension=256)

    # Populate SQLite with test documents
    with db.transaction() as conn:
        fld = FolderRepository.get_or_create(conn, str(tmp_path / "docs"))
        fid = FileRepository.upsert(
            conn,
            FileRecord(
                folder_id=fld.id,
                path=str(tmp_path / "docs" / "ai_paper.pdf"),
                filename="ai_paper.pdf",
                extension=".pdf",
                file_type="pdf",
                modified_at="2026-11-05T00:00:00Z",
                status="success",
            ),
        )
        chunks = [
            DocumentChunk(
                chunk_index=0,
                content="Deep learning transformers and neural network attention mechanism.",
                token_count=10,
                page_number=1,
            ),
            DocumentChunk(
                chunk_index=1,
                content="Relational SQL databases and transaction ACID normalization.",
                token_count=10,
                page_number=2,
            ),
        ]
        ChunkRepository.insert_chunks(conn, fid, chunks)

    # Sync chunks to vector store
    with db.connection() as conn:
        db_chunks = ChunkRepository.get_by_file_id(conn, fid)
    c_ids = [c.id for c in db_chunks]
    c_docs = [c.content for c in db_chunks]
    c_metas = [{"file_id": fid, "filename": "ai_paper.pdf", "file_type": "pdf", "folder_id": fld.id} for _ in db_chunks]
    vector_store.upsert(
        chunk_ids=c_ids,
        embeddings=embedder.embed_documents(c_docs),
        metadatas=c_metas,
        documents=c_docs,
    )

    kw_engine = KeywordSearchEngine(db=db)
    sem_engine = SemanticSearchEngine(db=db, vector_store=vector_store, embedder=embedder)
    hyb_engine = HybridSearchEngine(db=db, keyword_engine=kw_engine, semantic_engine=sem_engine)
    search_service = SearchService(
        keyword_engine=kw_engine,
        semantic_engine=sem_engine,
        hybrid_engine=hyb_engine,
    )

    app = create_app()
    app.dependency_overrides[get_search_engine] = lambda: kw_engine
    app.dependency_overrides[get_semantic_search_engine] = lambda: sem_engine
    app.dependency_overrides[get_hybrid_search_engine] = lambda: hyb_engine
    app.dependency_overrides[get_search_service] = lambda: search_service
    client = TestClient(app)

    return client, search_service


def test_unified_search_post_hybrid(search_service_env):
    """Verify POST /api/v1/search/unified with hybrid mode."""
    client, _ = search_service_env
    payload = {
        "query": "transformer neural network",
        "mode": "hybrid",
        "limit": 5,
        "offset": 0,
    }
    response = client.post("/api/v1/search/unified", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["query"] == "transformer neural network"
    assert data["requested_mode"] == "hybrid"
    assert data["effective_mode"] in ("hybrid", "keyword_only", "semantic_only")
    assert data["total_results"] >= 1
    assert len(data["results"]) >= 1
    assert "rrf_score" in data["results"][0]


def test_unified_search_post_keyword(search_service_env):
    """Verify POST /api/v1/search/unified with keyword mode."""
    client, _ = search_service_env
    payload = {
        "query": "relational SQL",
        "mode": "keyword",
        "limit": 5,
    }
    response = client.post("/api/v1/search/unified", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["requested_mode"] == "keyword"
    assert data["effective_mode"] == "keyword"
    assert data["total_results"] >= 1
    assert data["results"][0]["bm25_score"] is not None


def test_unified_search_post_semantic(search_service_env):
    """Verify POST /api/v1/search/unified with semantic mode."""
    client, _ = search_service_env
    payload = {
        "query": "artificial intelligence architecture",
        "mode": "semantic",
        "limit": 5,
    }
    response = client.post("/api/v1/search/unified", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["requested_mode"] == "semantic"
    assert data["effective_mode"] == "semantic"
    assert data["total_results"] >= 1
    assert data["results"][0]["cosine_similarity"] is not None


def test_unified_search_get(search_service_env):
    """Verify GET /api/v1/search/unified executes search via query parameters."""
    client, _ = search_service_env
    response = client.get("/api/v1/search/unified?q=transformer&mode=hybrid&limit=2")
    assert response.status_code == 200
    data = response.json()
    assert data["query"] == "transformer"
    assert data["requested_mode"] == "hybrid"
    assert len(data["results"]) <= 2


def test_unified_search_empty_query(search_service_env):
    """Verify empty query string returns zero results."""
    client, search_service = search_service_env
    res = search_service.search("   ", mode=SearchModeEnum.HYBRID)
    assert res.total_results == 0
    assert len(res.results) == 0


def test_unified_search_file_type_filter(search_service_env):
    """Verify file_types filter applies to unified search query."""
    client, _ = search_service_env
    payload = {
        "query": "transformer",
        "mode": "hybrid",
        "filter": {"file_types": ["pdf"]},
    }
    response = client.post("/api/v1/search/unified", json=payload)
    assert response.status_code == 200
    data = response.json()
    for item in data["results"]:
        assert item["file_type"] == "pdf"

