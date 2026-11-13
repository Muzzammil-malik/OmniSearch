"""Comprehensive end-to-end tests for media format search filtering (Images, Audio, Video).

Verifies strict category isolation, alias normalization, and cross-modality retrieval across:
- KeywordSearchEngine (SQLite FTS5 BM25)
- SemanticSearchEngine (ChromaDB vector similarity)
- HybridSearchEngine (RRF fusion)
- UnifiedSearch / API endpoints
"""

import math
from pathlib import Path
import pytest
from PIL import Image
import wave
import struct

from app.database.connection import DatabaseConnectionManager
from app.database.initialization import init_db
from app.database.repositories.folders import FolderRepository
from app.embeddings.test_embedder import DeterministicTestEmbedder
from app.ingestion.file_detector import FileTypeDetector
from app.schemas.search import (
    HybridSearchQuery,
    SearchFilter,
    SearchQuery,
    SemanticSearchQuery,
    UnifiedSearchQuery,
)
from app.search.filter_utils import normalize_file_type_filters
from app.search.hybrid_search import HybridSearchEngine
from app.search.keyword_search import KeywordSearchEngine
from app.search.semantic_search import SemanticSearchEngine
from app.services.indexer import IndexingService
from app.services.search_service import SearchService
from app.services.semantic_pipeline import SemanticPipeline
from app.vector_store.chroma import ChromaVectorStore


# ---------------------------------------------------------------------------
# Test Helpers to generate genuine media files
# ---------------------------------------------------------------------------

from tests.test_multimodal import create_test_image, create_test_video, create_test_wav


# ---------------------------------------------------------------------------
# 1. Filter Normalization Unit Tests
# ---------------------------------------------------------------------------

def test_normalize_file_type_filters_categories():
    """Verify alias mapping for images, audio, video, sheets, markdown, etc."""
    assert normalize_file_type_filters(["image"]) == ["image"]
    assert normalize_file_type_filters(["images"]) == ["image"]
    assert normalize_file_type_filters(["IMAGE"]) == ["image"]

    assert normalize_file_type_filters(["audio"]) == ["audio"]
    assert normalize_file_type_filters(["audios"]) == ["audio"]

    assert normalize_file_type_filters(["video"]) == ["video"]
    assert normalize_file_type_filters(["videos"]) == ["video"]

    assert normalize_file_type_filters(["sheets"]) == ["xlsx", "csv"]
    assert normalize_file_type_filters(["xlsx"]) == ["xlsx", "csv"]

    assert normalize_file_type_filters(["md"]) == ["markdown"]
    assert normalize_file_type_filters(["markdown"]) == ["markdown"]

    assert normalize_file_type_filters(["code"]) == ["code"]
    assert normalize_file_type_filters(["text"]) == ["text"]
    assert normalize_file_type_filters(["txt"]) == ["text"]


def test_normalize_file_type_filters_extensions():
    """Verify individual file extensions are converted to format categories."""
    assert normalize_file_type_filters([".png"]) == ["image"]
    assert normalize_file_type_filters(["jpg"]) == ["image"]
    assert normalize_file_type_filters([".mp3"]) == ["audio"]
    assert normalize_file_type_filters(["wav"]) == ["audio"]
    assert normalize_file_type_filters([".mp4"]) == ["video"]
    assert normalize_file_type_filters(["mkv"]) == ["video"]
    assert normalize_file_type_filters([".py"]) == ["code"]


def test_normalize_file_type_filters_empty_and_invalid():
    """Verify empty or None inputs return None safely."""
    assert normalize_file_type_filters(None) is None
    assert normalize_file_type_filters([]) is None
    assert normalize_file_type_filters(["", "  "]) is None


def test_file_detector_new_multimedia_extensions():
    """Verify extended multimedia formats are recognized by FileTypeDetector."""
    assert FileTypeDetector.is_supported_extension(".tif")
    assert FileTypeDetector.get_format_category(".tif") == "image"

    assert FileTypeDetector.is_supported_extension(".oga")
    assert FileTypeDetector.get_format_category(".oga") == "audio"
    assert FileTypeDetector.is_supported_extension(".opus")
    assert FileTypeDetector.get_format_category(".opus") == "audio"
    assert FileTypeDetector.is_supported_extension(".wma")
    assert FileTypeDetector.get_format_category(".wma") == "audio"

    assert FileTypeDetector.is_supported_extension(".wmv")
    assert FileTypeDetector.get_format_category(".wmv") == "video"
    assert FileTypeDetector.is_supported_extension(".m4v")
    assert FileTypeDetector.get_format_category(".m4v") == "video"
    assert FileTypeDetector.is_supported_extension(".mpeg")
    assert FileTypeDetector.get_format_category(".mpeg") == "video"
    assert FileTypeDetector.get_format_category(".mpg") == "video"


# ---------------------------------------------------------------------------
# 2. Multi-Format Search Environment Fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def multi_format_env(tmp_path: Path):
    """Set up indexed repository containing Text, Code, PDF/Doc, Image, Audio, and Video files."""
    db_file = tmp_path / "multiformat.db"
    vectors_dir = tmp_path / "vectors"
    library_dir = tmp_path / "library"
    library_dir.mkdir()

    # 1. Create Media Files with distinct keywords in filename and content
    img1 = library_dir / "mountain_sunrise.png"
    create_test_image(img1, color=(255, 120, 40))

    audio1 = library_dir / "acoustic_guitar.wav"
    create_test_wav(audio1, duration_sec=1.5)

    vid1 = library_dir / "mountain_hike.mp4"
    create_test_video(vid1)

    # 2. Create Text and Code Files
    txt1 = library_dir / "mountain_expedition_notes.txt"
    txt1.write_text("Notes from the expedition to the high mountain peak.", encoding="utf-8")

    code1 = library_dir / "mountain_elevation.py"
    code1.write_text("def calculate_mountain_altitude(pressure: float) -> float:\n    return pressure * 10.5\n", encoding="utf-8")

    # 3. Initialize DB and Services
    db = init_db(db_file)
    vector_store = ChromaVectorStore(persist_dir=vectors_dir)
    embedder = DeterministicTestEmbedder(dimension=768)
    pipeline = SemanticPipeline(db=db, embedder=embedder, vector_store=vector_store)
    indexer = IndexingService(db=db, semantic_pipeline=pipeline)

    with db.connection() as conn:
        FolderRepository.get_or_create(conn, str(library_dir))

    indexer.index_folder(library_dir, generate_embeddings=True)

    keyword_engine = KeywordSearchEngine(db=db)
    semantic_engine = SemanticSearchEngine(db=db, vector_store=vector_store, embedder=embedder)
    hybrid_engine = HybridSearchEngine(db=db, keyword_engine=keyword_engine, semantic_engine=semantic_engine)
    search_service = SearchService(
        keyword_engine=keyword_engine,
        semantic_engine=semantic_engine,
        hybrid_engine=hybrid_engine,
    )

    return {
        "db": db,
        "vector_store": vector_store,
        "embedder": embedder,
        "keyword_engine": keyword_engine,
        "semantic_engine": semantic_engine,
        "hybrid_engine": hybrid_engine,
        "search_service": search_service,
    }


# ---------------------------------------------------------------------------
# 3. Keyword Search Media Filter Tests
# ---------------------------------------------------------------------------

def test_keyword_search_image_filter(multi_format_env):
    """Verify Keyword search with file_types=['image'] matches only image items."""
    engine: KeywordSearchEngine = multi_format_env["keyword_engine"]

    filt = SearchFilter(file_types=["image"])
    res = engine.search("mountain", filters=filt)

    assert res.total_results > 0
    assert len(res.results) > 0
    for r in res.results:
        assert r.file_type == "image"
        assert r.content_type == "image"
        assert r.filename.endswith(".png")


def test_keyword_search_audio_filter(multi_format_env):
    """Verify Keyword search with file_types=['audio'] matches only audio items."""
    engine: KeywordSearchEngine = multi_format_env["keyword_engine"]

    filt = SearchFilter(file_types=["audio"])
    res = engine.search("guitar", filters=filt)

    assert res.total_results == 1
    item = res.results[0]
    assert item.file_type == "audio"
    assert item.content_type == "audio"
    assert item.filename == "acoustic_guitar.wav"


def test_keyword_search_video_filter(multi_format_env):
    """Verify Keyword search with file_types=['video'] matches only video items."""
    engine: KeywordSearchEngine = multi_format_env["keyword_engine"]

    filt = SearchFilter(file_types=["video"])
    res = engine.search("mountain", filters=filt)

    assert res.total_results == 1
    item = res.results[0]
    assert item.file_type == "video"
    assert item.content_type == "video"
    assert item.filename == "mountain_hike.mp4"


def test_keyword_search_media_isolation_no_leakage(multi_format_env):
    """Verify querying 'mountain' across categories never leaks non-matching file types."""
    engine: KeywordSearchEngine = multi_format_env["keyword_engine"]

    # Image filter should not return .txt or .py
    res_img = engine.search("mountain", filters=SearchFilter(file_types=["images"]))
    for r in res_img.results:
        assert r.file_type == "image"
        assert r.content_type == "image"

    # Code filter should not return .png or .mp4
    res_code = engine.search("mountain", filters=SearchFilter(file_types=["code"]))
    for r in res_code.results:
        assert r.file_type == "code"
        assert r.content_type == "document"

    # Text filter should not return .png or .mp4
    res_txt = engine.search("mountain", filters=SearchFilter(file_types=["text"]))
    for r in res_txt.results:
        assert r.file_type == "text"
        assert r.content_type == "document"


# ---------------------------------------------------------------------------
# 4. Semantic Search Media Filter Tests
# ---------------------------------------------------------------------------

def test_semantic_search_media_filters(multi_format_env):
    """Verify Semantic search filters by image, audio, and video categories."""
    engine: SemanticSearchEngine = multi_format_env["semantic_engine"]

    # Semantic search with Image filter
    res_img = engine.search("scenic mountain landscape", filters=SearchFilter(file_types=["image"]))
    assert len(res_img.results) > 0
    for r in res_img.results:
        assert r.file_type == "image"
        assert r.content_type == "image"

    # Semantic search with Audio filter
    res_audio = engine.search("musical acoustic performance", filters=SearchFilter(file_types=["audio"]))
    assert len(res_audio.results) > 0
    for r in res_audio.results:
        assert r.file_type == "audio"
        assert r.content_type == "audio"

    # Semantic search with Video filter
    res_vid = engine.search("mountain hike footage", filters=SearchFilter(file_types=["video"]))
    assert len(res_vid.results) > 0
    for r in res_vid.results:
        assert r.file_type == "video"
        assert r.content_type == "video"


# ---------------------------------------------------------------------------
# 5. Hybrid Search Media Filter Tests
# ---------------------------------------------------------------------------

def test_hybrid_search_media_filters(multi_format_env):
    """Verify Hybrid RRF search honors image, audio, and video format filters."""
    engine: HybridSearchEngine = multi_format_env["hybrid_engine"]

    # Hybrid Image filter
    res_img = engine.search("mountain sunrise", filters=SearchFilter(file_types=["images"]))
    assert res_img.total_results > 0
    for r in res_img.results:
        assert r.file_type == "image"
        assert r.content_type == "image"

    # Hybrid Audio filter
    res_audio = engine.search("guitar melody", filters=SearchFilter(file_types=["audios"]))
    assert res_audio.total_results > 0
    for r in res_audio.results:
        assert r.file_type == "audio"
        assert r.content_type == "audio"

    # Hybrid Video filter
    res_vid = engine.search("mountain hike", filters=SearchFilter(file_types=["videos"]))
    assert res_vid.total_results > 0
    for r in res_vid.results:
        assert r.file_type == "video"
        assert r.content_type == "video"


# ---------------------------------------------------------------------------
# 6. Unified Search Service Media Filter Tests
# ---------------------------------------------------------------------------

def test_unified_search_service_media_filters(multi_format_env):
    """Verify SearchService unified endpoint supports media format filtering in all modes."""
    service: SearchService = multi_format_env["search_service"]

    # Unified hybrid search with image filter
    req = UnifiedSearchQuery(
        query="mountain",
        filter=SearchFilter(file_types=["image"]),
    )
    res = service.search(req)
    assert res.total_results > 0
    for r in res.results:
        assert r.file_type == "image"
        assert r.content_type == "image"

    # Unified keyword mode with video filter
    req_kw = UnifiedSearchQuery(
        query="mountain",
        mode="keyword",
        filter=SearchFilter(file_types=["video"]),
    )
    res_kw = service.search(req_kw)
    assert res_kw.total_results == 1
    assert res_kw.results[0].file_type == "video"
    assert res_kw.results[0].content_type == "video"
