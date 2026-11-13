"""Tests for native dependency classification, lifecycle management, failure caching, and graceful degradation."""

from unittest.mock import MagicMock, patch
import pytest

from app.core.dependencies import (
    ChromaDependencyError,
    ChromaDependencyManager,
    NativeDependencyError,
    PyTorchDependencyError,
    ScipyDependencyManager,
    TorchDependencyManager,
    classify_native_error,
)
from app.schemas.search import (
    HybridSearchQuery,
    SearchQuery,
    SearchResponse,
    SearchResultItem,
)
from app.search.hybrid_search import HybridSearchEngine
from app.vector_store.chroma import (
    ChromaVectorStore,
    VectorStoreUnavailableError,
)


# =====================================================================
# 1. Classification Tests
# =====================================================================

def test_classify_native_error_application_control_winerror():
    exc = OSError("[WinError 4551] The operating system cannot run %1. Smart App Control or Windows Defender Application Control blocked it.")
    exc.winerror = 4551
    assert classify_native_error(exc) == "application_control_policy_blocked"


def test_classify_native_error_application_control_message_without_winerror():
    exc = RuntimeError("Import failed due to Application Control policy enforcement")
    assert classify_native_error(exc) == "application_control_policy_blocked"


def test_classify_native_error_smart_app_control():
    exc = ImportError("DLL load failed: blocked by smart app control")
    assert classify_native_error(exc) == "application_control_policy_blocked"


def test_classify_native_error_native_dll_shm():
    exc = OSError("Error loading \"torch\\lib\\shm.dll\" or one of its dependencies")
    assert classify_native_error(exc) == "native_dll_load_failed"


def test_classify_native_error_native_dll_cygrpc():
    exc = ImportError("cannot import name 'cygrpc' from 'grpc._cython'")
    assert classify_native_error(exc) == "native_dll_load_failed"


def test_classify_native_error_winerror_126():
    exc = OSError("[WinError 126] The specified module could not be found")
    exc.winerror = 126
    assert classify_native_error(exc) == "native_dll_load_failed"


def test_classify_native_error_not_installed():
    exc = ModuleNotFoundError("No module named 'foobar_ml'")
    assert classify_native_error(exc) == "not_installed"


def test_classify_native_error_generic():
    exc = ValueError("Unexpected configuration error")
    assert classify_native_error(exc) == "initialization_failed"


# =====================================================================
# 2. TorchDependencyManager Tests
# =====================================================================

def test_torch_dependency_manager_singleton():
    TorchDependencyManager.reset_instance()
    mgr1 = TorchDependencyManager.get_instance()
    mgr2 = TorchDependencyManager.get_instance()
    assert mgr1 is mgr2
    TorchDependencyManager.reset_instance()


def test_torch_dependency_manager_cached_failure():
    TorchDependencyManager.reset_instance()
    mgr = TorchDependencyManager()

    # Simulate import failure
    fake_exc = OSError("[WinError 4551] Blocked by Code Integrity")
    fake_exc.winerror = 4551

    with patch.object(mgr, "_import_torch", side_effect=fake_exc):
        with pytest.raises(PyTorchDependencyError) as exc_info:
            mgr.ensure_torch()

        assert exc_info.value.category == "application_control_policy_blocked"
        assert exc_info.value.original_exception is fake_exc
        assert not mgr.is_available()
        assert mgr.get_error_category() == "application_control_policy_blocked"
        assert mgr.get_original_exception() is fake_exc

        # Secondary call must return cached failure without re-attempting import
        with pytest.raises(PyTorchDependencyError) as exc_info2:
            mgr.ensure_torch()
        assert exc_info2.value.category == "application_control_policy_blocked"
        assert exc_info2.value.original_exception is fake_exc


def test_torch_dependency_manager_success():
    TorchDependencyManager.reset_instance()
    mgr = TorchDependencyManager()

    fake_torch = MagicMock()
    fake_torch.__version__ = "2.15.0+cpu"

    with patch.object(mgr, "_import_torch", return_value=fake_torch):
        mod = mgr.ensure_torch()
        assert mod is fake_torch
        assert mgr.is_available()
        assert mgr.get_version() == "2.15.0+cpu"


# =====================================================================
# 3. ChromaDependencyManager Tests
# =====================================================================

def test_chroma_dependency_manager_singleton():
    ChromaDependencyManager.reset_instance()
    mgr1 = ChromaDependencyManager.get_instance()
    mgr2 = ChromaDependencyManager.get_instance()
    assert mgr1 is mgr2
    ChromaDependencyManager.reset_instance()


def test_chroma_dependency_manager_cached_failure():
    ChromaDependencyManager.reset_instance()
    mgr = ChromaDependencyManager()

    fake_exc = ImportError("cannot import name 'cygrpc' from 'grpc._cython'")

    with patch.object(mgr, "_import_chromadb", side_effect=fake_exc):
        with pytest.raises(ChromaDependencyError) as exc_info:
            mgr.ensure_chromadb()

        assert exc_info.value.category == "native_dll_load_failed"
        assert exc_info.value.original_exception is fake_exc
        assert not mgr.is_available()

        # Second call raises cached error
        with pytest.raises(ChromaDependencyError):
            mgr.ensure_chromadb()


# =====================================================================
# 4. ChromaVectorStore Error Reporting Tests
# =====================================================================

def test_chroma_vector_store_unavailable_raises_not_zero():
    """Verify count() and get_all_chunk_ids() do NOT mask unavailable vector store as 0 or empty set."""
    with patch("app.vector_store.chroma.ChromaDependencyManager.get_instance") as mock_dep_mgr:
        fake_mgr = MagicMock()
        fake_mgr.is_available.return_value = False
        fake_mgr.ensure_chromadb.side_effect = ChromaDependencyError(
            "ChromaDB blocked by policy",
            category="application_control_policy_blocked",
            original_exception=OSError("[WinError 4551] Blocked"),
        )
        fake_mgr.get_error_category.return_value = "application_control_policy_blocked"
        fake_mgr.get_original_exception.return_value = OSError("[WinError 4551] Blocked")
        mock_dep_mgr.return_value = fake_mgr

        vs = ChromaVectorStore(persist_dir="/tmp/fake_chroma_test")
        assert not vs.is_available()
        assert vs.get_error_category() == "application_control_policy_blocked"

        with pytest.raises(VectorStoreUnavailableError) as exc1:
            vs.count()
        assert "unavailable" in str(exc1.value).lower()

        with pytest.raises(VectorStoreUnavailableError) as exc2:
            vs.get_all_chunk_ids()
        assert "unavailable" in str(exc2.value).lower()


# =====================================================================
# 5. Hybrid Search Graceful Degradation Tests
# =====================================================================

def test_hybrid_search_graceful_degradation_when_semantic_unavailable():
    """Verify hybrid search falls back to keyword-only search when semantic search fails."""
    mock_kw = MagicMock()
    mock_kw.search.return_value = SearchResponse(
        query="OmniSearch",
        total_results=1,
        results=[
            SearchResultItem(
                chunk_id=1,
                file_id=1,
                file_path="C:/docs/report.txt",
                filename="report.txt",
                file_type="txt",
                content_type="document",
                file_status="indexed",
                chunk_index=0,
                content="OmniSearch project details",
                snippet="OmniSearch project details",
                score=1.0,
                bm25_rank=-1.0,
            )
        ],
        limit=10,
        offset=0,
        execution_time_ms=5.0,
    )

    mock_sem = MagicMock()
    mock_sem.search.side_effect = VectorStoreUnavailableError("Vector store unavailable (application_control_policy_blocked)")

    mock_db = MagicMock()

    hybrid = HybridSearchEngine(
        db=mock_db,
        keyword_engine=mock_kw,
        semantic_engine=mock_sem,
        use_concurrency=False,
    )

    query = HybridSearchQuery(query="OmniSearch", limit=10)
    response = hybrid.search(query)

    # Must succeed, return keyword results, and indicate fallback reason
    assert len(response.results) == 1
    assert response.results[0].chunk_id == 1
    assert response.search_mode == "keyword_only"
    assert response.keyword_available is True
    assert response.semantic_available is False
    assert response.fallback_reason is not None
    assert "Vector store unavailable" in response.fallback_reason


# =====================================================================
# 6. Indexing & Embedding Ambiguity Handling Tests
# =====================================================================

def test_semantic_pipeline_skips_when_zero_unembedded():
    """Verify sync_embeddings immediately returns 0 without calling embedder when 0 unembedded chunks."""
    from app.services.semantic_pipeline import SemanticPipeline

    mock_db = MagicMock()
    mock_conn = MagicMock()
    mock_db.connection.return_value.__enter__.return_value = mock_conn

    # Mock get_unembedded_chunks to return empty list
    with patch("app.database.repositories.embeddings.ChunkEmbeddingRepository.get_unembedded_chunks", return_value=[]):
        mock_vs = MagicMock()
        mock_vs.is_available.return_value = True
        mock_embedder = MagicMock()

        pipeline = SemanticPipeline(db=mock_db, embedder=mock_embedder, vector_store=mock_vs)
        count = pipeline.sync_embeddings()

        assert count == 0
        mock_embedder.embed_documents.assert_not_called()


def test_semantic_pipeline_raises_when_vector_store_unavailable():
    """Verify sync_embeddings raises VectorStoreUnavailableError when vector store is not operational."""
    from app.services.semantic_pipeline import SemanticPipeline

    mock_db = MagicMock()
    mock_conn = MagicMock()
    mock_db.connection.return_value.__enter__.return_value = mock_conn

    with patch("app.database.repositories.embeddings.ChunkEmbeddingRepository.get_unembedded_chunks", return_value=[{"chunk_id": 1}]):
        mock_vs = MagicMock()
        mock_vs.is_available.return_value = False
        mock_vs._init_error = OSError("[WinError 4551] Blocked")
        mock_embedder = MagicMock()

        pipeline = SemanticPipeline(db=mock_db, embedder=mock_embedder, vector_store=mock_vs)

        with pytest.raises(VectorStoreUnavailableError) as exc_info:
            pipeline.sync_embeddings()

        assert "Vector store is unavailable" in str(exc_info.value)


# =====================================================================
# 7. Scipy Dependency & Capability Detection Tests
# =====================================================================

def test_scipy_dependency_manager_case_a_normally_available():
    """Case A: SciPy is installed and importable normally."""
    import sys
    ScipyDependencyManager.reset_instance()
    mgr = ScipyDependencyManager()

    fake_scipy = MagicMock()
    fake_scipy.__version__ = "1.15.0"

    with patch("importlib.util.find_spec", return_value=MagicMock()):
        with patch.object(mgr, "_probe_scipy", return_value=fake_scipy):
            assert mgr.check_capability() is True
            assert mgr.is_available() is True
            assert mgr.is_blocked() is False
    ScipyDependencyManager.reset_instance()


def test_scipy_dependency_manager_case_b_not_installed():
    """Case B: SciPy is not installed."""
    ScipyDependencyManager.reset_instance()
    mgr = ScipyDependencyManager()

    with patch("importlib.util.find_spec", return_value=None):
        assert mgr.check_capability() is False
        assert mgr.is_available() is False
        assert mgr.is_blocked() is False
    ScipyDependencyManager.reset_instance()


def test_scipy_dependency_manager_case_c_package_exists_but_native_blocked():
    """Case C: SciPy package exists on disk but native binary import is blocked by policy."""
    import sys
    ScipyDependencyManager.reset_instance()
    mgr = ScipyDependencyManager()

    fake_exc = ImportError("[WinError 4551] An Application Control policy has blocked this file: _ccallback_c.pyd")
    fake_exc.winerror = 4551

    with patch("importlib.util.find_spec", return_value=MagicMock()):
        with patch.object(mgr, "_probe_scipy", side_effect=fake_exc):
            assert mgr.check_capability() is False
            assert mgr.is_available() is False
            assert mgr.is_blocked() is True
            assert mgr.get_error_category() == "application_control_policy_blocked"
            # Ensure sys.modules["scipy"] is safely set to None so transformers skips DETR loss imports
            assert sys.modules.get("scipy") is None
    ScipyDependencyManager.reset_instance()


