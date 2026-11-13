"""Comprehensive test suite for Library Folder Search Scope Selector.

Validates end-to-end folder scoping across:
1. Pydantic request schema normalization (library_folder_id, folder_id, SearchFilter)
2. Keyword search engine (SQLite FTS5 BM25 with folder_id constraint)
3. Semantic search engine (ChromaDB vector query + SQLite verification)
4. Hybrid search engine (RRF candidate pool constraint)
5. SearchService & Unified search endpoint (combining folder scope and format filters)
"""

import json
from pathlib import Path
import pytest

from app.database.connection import DatabaseConnectionManager
from app.database.initialization import init_db
from app.database.repositories.folders import FolderRepository
from app.embeddings.test_embedder import DeterministicTestEmbedder
from app.schemas.search import (
    HybridSearchQuery,
    SearchFilter,
    SearchModeEnum,
    SearchQuery,
    SemanticSearchQuery,
    UnifiedSearchQuery,
)
from app.search.hybrid_search import HybridSearchEngine
from app.search.keyword_search import KeywordSearchEngine
from app.search.semantic_search import SemanticSearchEngine
from app.services.indexer import IndexingService
from app.services.search_service import SearchService
from app.services.semantic_pipeline import SemanticPipeline
from app.vector_store.chroma import ChromaVectorStore


# ==============================================================================
# 1. Schema & Normalization Unit Tests
# ==============================================================================

def test_search_filter_effective_folder_ids():
    """Verify get_effective_folder_ids combines folder_ids, folder_id, and library_folder_id."""
    f1 = SearchFilter(folder_ids=[1, 2])
    assert f1.get_effective_folder_ids() == [1, 2]

    f2 = SearchFilter(folder_id=3)
    assert f2.get_effective_folder_ids() == [3]

    f3 = SearchFilter(library_folder_id=4)
    assert f3.get_effective_folder_ids() == [4]

    f4 = SearchFilter(folder_ids=[1], folder_id=2, library_folder_id=3)
    assert f4.get_effective_folder_ids() == [1, 2, 3]

    # Deduplication
    f5 = SearchFilter(folder_ids=[5, 6], folder_id=5, library_folder_id=6)
    assert f5.get_effective_folder_ids() == [5, 6]

    # None when empty
    f6 = SearchFilter()
    assert f6.get_effective_folder_ids() is None


def test_search_query_scope_sync():
    """Verify SearchQuery auto-populates filter.folder_ids from root folder_id or library_folder_id."""
    q1 = SearchQuery(query="financial", library_folder_id=10)
    assert q1.filter is not None
    assert q1.filter.folder_ids == [10]

    q2 = SearchQuery(query="financial", folder_id=20)
    assert q2.filter is not None
    assert q2.filter.folder_ids == [20]

    # Preserves existing filter properties
    q3 = SearchQuery(
        query="financial",
        library_folder_id=30,
        filter=SearchFilter(file_types=["pdf"]),
    )
    assert q3.filter.file_types == ["pdf"]
    assert 30 in q3.filter.folder_ids


def test_semantic_hybrid_unified_query_scope_sync():
    """Verify Semantic, Hybrid, and Unified query schemas sync folder scope."""
    sem = SemanticSearchQuery(query="revenue analysis", library_folder_id=42)
    assert sem.filter is not None
    assert sem.filter.folder_ids == [42]

    hyb = HybridSearchQuery(query="revenue analysis", folder_id=99)
    assert hyb.filter is not None
    assert hyb.filter.folder_ids == [99]

    uni = UnifiedSearchQuery(
        query="revenue analysis",
        mode=SearchModeEnum.HYBRID,
        library_folder_id=77,
        filter=SearchFilter(file_types=["image"]),
    )
    assert uni.filter.file_types == ["image"]
    assert uni.filter.folder_ids == [77]


# ==============================================================================
# 2. End-to-End Search Engines with Scoped Multi-Folder Setup
# ==============================================================================

@pytest.fixture
def scoped_search_fixture(tmp_path: Path):
    """Fixture initializing a SQLite database, two library folders, indexed content, and vector store."""
    db_path = tmp_path / "omnisearch_test.db"
    db = init_db(db_path)

    chroma_dir = tmp_path / "chroma_db"
    vector_store = ChromaVectorStore(persist_dir=chroma_dir)
    embedder = DeterministicTestEmbedder(dimension=64)
    semantic_pipeline = SemanticPipeline(
        db=db,
        vector_store=vector_store,
        embedder=embedder,
        batch_size=10,
    )

    indexer = IndexingService(
        db=db,
        semantic_pipeline=semantic_pipeline,
    )

    # Folder 1: "Work Projects"
    folder1_path = tmp_path / "Work_Projects"
    folder1_path.mkdir()
    doc1 = folder1_path / "quarterly_budget.txt"
    doc1.write_text("Quarterly financial budget forecast for company operations in Q4.", encoding="utf-8")

    # Folder 2: "Personal Archives"
    folder2_path = tmp_path / "Personal_Archives"
    folder2_path.mkdir()
    doc2 = folder2_path / "vacation_expenses.txt"
    doc2.write_text("Quarterly financial holiday expenses and family vacation budget.", encoding="utf-8")

    # Register folders in DB
    with db.connection() as conn:
        f1_row = FolderRepository.get_or_create(conn, str(folder1_path))
        f2_row = FolderRepository.get_or_create(conn, str(folder2_path))

    # Index both folders
    indexer.index_folder(folder1_path, generate_embeddings=True)
    indexer.index_folder(folder2_path, generate_embeddings=True)

    keyword_engine = KeywordSearchEngine(db=db)
    semantic_engine = SemanticSearchEngine(
        db=db,
        vector_store=vector_store,
        embedder=embedder,
    )
    hybrid_engine = HybridSearchEngine(
        db=db,
        keyword_engine=keyword_engine,
        semantic_engine=semantic_engine,
    )
    search_service = SearchService(
        keyword_engine=keyword_engine,
        semantic_engine=semantic_engine,
        hybrid_engine=hybrid_engine,
    )

    return {
        "db": db,
        "folder1": f1_row,
        "folder2": f2_row,
        "keyword_engine": keyword_engine,
        "semantic_engine": semantic_engine,
        "hybrid_engine": hybrid_engine,
        "search_service": search_service,
    }


def test_keyword_search_folder_scoping(scoped_search_fixture):
    """Keyword search restricted to folder1 should never return results from folder2."""
    fx = scoped_search_fixture
    f1_id = fx["folder1"].id
    f2_id = fx["folder2"].id
    engine: KeywordSearchEngine = fx["keyword_engine"]

    # Scope to Folder 1
    res1 = engine.search(SearchQuery(
        query="quarterly financial",
        library_folder_id=f1_id,
    ))
    assert res1.total_results == 1
    assert "quarterly_budget.txt" in res1.results[0].filename

    # Scope to Folder 2
    res2 = engine.search(SearchQuery(
        query="quarterly financial",
        library_folder_id=f2_id,
    ))
    assert res2.total_results == 1
    assert "vacation_expenses.txt" in res2.results[0].filename

    # All folders (no folder scope)
    res_all = engine.search(SearchQuery(
        query="quarterly financial",
        library_folder_id=None,
    ))
    assert res_all.total_results == 2
    filenames = {r.filename for r in res_all.results}
    assert "quarterly_budget.txt" in filenames
    assert "vacation_expenses.txt" in filenames


def test_semantic_search_folder_scoping(scoped_search_fixture):
    """Semantic vector search restricted to a specific folder returns only chunks from that folder."""
    fx = scoped_search_fixture
    f1_id = fx["folder1"].id
    f2_id = fx["folder2"].id
    engine: SemanticSearchEngine = fx["semantic_engine"]

    # Scope to Folder 1
    res1 = engine.search(SemanticSearchQuery(
        query="quarterly budget forecast",
        library_folder_id=f1_id,
    ))
    assert res1.total_results >= 1
    for r in res1.results:
        assert r.filename == "quarterly_budget.txt"

    # Scope to Folder 2
    res2 = engine.search(SemanticSearchQuery(
        query="vacation holiday expenses",
        library_folder_id=f2_id,
    ))
    assert res2.total_results >= 1
    for r in res2.results:
        assert r.filename == "vacation_expenses.txt"


def test_hybrid_search_folder_scoping(scoped_search_fixture):
    """Hybrid RRF search strictly bounds both keyword and semantic candidate pools."""
    fx = scoped_search_fixture
    f1_id = fx["folder1"].id
    f2_id = fx["folder2"].id
    engine: HybridSearchEngine = fx["hybrid_engine"]

    res_f1 = engine.search(HybridSearchQuery(
        query="quarterly financial",
        library_folder_id=f1_id,
    ))
    assert res_f1.total_results == 1
    assert res_f1.results[0].filename == "quarterly_budget.txt"

    res_f2 = engine.search(HybridSearchQuery(
        query="quarterly financial",
        library_folder_id=f2_id,
    ))
    assert res_f2.total_results == 1
    assert res_f2.results[0].filename == "vacation_expenses.txt"


def test_unified_search_service_scoping(scoped_search_fixture):
    """Unified search service properly forwards folder scope across hybrid, keyword, and semantic modes."""
    fx = scoped_search_fixture
    f1_id = fx["folder1"].id
    f2_id = fx["folder2"].id
    service: SearchService = fx["search_service"]

    # Unified Hybrid
    resp_hybrid = service.search(UnifiedSearchQuery(
        query="budget expenses",
        mode=SearchModeEnum.HYBRID,
        library_folder_id=f1_id,
    ))
    assert all(r.filename == "quarterly_budget.txt" for r in resp_hybrid.results)

    # Unified Keyword
    resp_kw = service.search(UnifiedSearchQuery(
        query="budget expenses",
        mode=SearchModeEnum.KEYWORD,
        library_folder_id=f2_id,
    ))
    assert all(r.filename == "vacation_expenses.txt" for r in resp_kw.results)

    # Unified Semantic
    resp_sem = service.search(UnifiedSearchQuery(
        query="budget expenses",
        mode=SearchModeEnum.SEMANTIC,
        library_folder_id=f1_id,
    ))
    assert all(r.filename == "quarterly_budget.txt" for r in resp_sem.results)


def test_nonexistent_folder_scope_returns_empty(scoped_search_fixture):
    """Scoping to a folder ID that has no indexed documents returns 0 results cleanly without errors."""
    fx = scoped_search_fixture
    service: SearchService = fx["search_service"]

    resp = service.search(UnifiedSearchQuery(
        query="quarterly financial",
        library_folder_id=999999,
    ))
    assert resp.total_results == 0
    assert len(resp.results) == 0


def test_guess_media_type_all_formats():
    """Verify MIME mapping covers images, video, audio, and documents correctly."""
    from app.api.v1.endpoints.system import guess_media_type

    assert guess_media_type(Path("photo.jpg")) == "image/jpeg"
    assert guess_media_type(Path("photo.png")) == "image/png"
    assert guess_media_type(Path("photo.webp")) == "image/webp"
    assert guess_media_type(Path("photo.gif")) == "image/gif"
    assert guess_media_type(Path("song.mp3")) == "audio/mpeg"
    assert guess_media_type(Path("song.wav")) == "audio/wav"
    assert guess_media_type(Path("song.flac")) == "audio/flac"
    assert guess_media_type(Path("song.ogg")) == "audio/ogg"
    assert guess_media_type(Path("movie.mp4")) == "video/mp4"
    assert guess_media_type(Path("movie.webm")) == "video/webm"
    assert guess_media_type(Path("doc.pdf")) == "application/pdf"


def test_preview_serving_and_security(scoped_search_fixture, tmp_path: Path):
    """Verify file-content endpoint serves authorized media with inline headers and blocks unauthorized files."""
    from fastapi import HTTPException
    from app.api.v1.endpoints.system import get_file_content

    fx = scoped_search_fixture
    db = fx["db"]

    # 1. Test existing indexed file in Folder 1
    f1_dir = Path(fx["folder1"].path)
    sample_img = f1_dir / "diagram.png"
    sample_img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 32)

    resp = get_file_content(path=str(sample_img), db=db)
    assert resp.media_type == "image/png"
    assert "inline" in resp.headers.get("content-disposition", "")
    assert resp.headers.get("accept-ranges") == "bytes"

    # 2. Test missing file inside library raises 404
    missing_file = f1_dir / "does_not_exist.png"
    with pytest.raises(HTTPException) as exc_404:
        get_file_content(path=str(missing_file), db=db)
    assert exc_404.value.status_code == 404

    # 3. Test unauthorized path outside library raises 403 Forbidden
    outside_file = tmp_path / "system_secret.txt"
    outside_file.write_text("classified", encoding="utf-8")
    with pytest.raises(HTTPException) as exc_403:
        get_file_content(path=str(outside_file), db=db)
    assert exc_403.value.status_code == 403

