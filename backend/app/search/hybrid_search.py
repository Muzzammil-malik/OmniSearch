"""Hybrid search engine combining lexical (FTS5 BM25) and semantic (ChromaDB) retrieval with RRF."""

from concurrent.futures import ThreadPoolExecutor
import time
from typing import Any, Dict, List, Optional, Union

from app.core.logging import get_logger
from app.database.connection import DatabaseConnectionManager
from app.schemas.search import (
    HybridSearchQuery,
    HybridSearchResponse,
    HybridSearchResultItem,
    SearchFilter,
    SearchResultItem,
    SemanticSearchResultItem,
)
from app.search.keyword_search import KeywordSearchEngine
from app.search.rrf import FusedCandidate, ReciprocalRankFusion
from app.search.semantic_search import SemanticSearchEngine

logger = get_logger(__name__)

_DEFAULT_KW = object()


class HybridSearchEngine:
    """Production hybrid search engine combining FTS5 keyword and ChromaDB semantic searches via RRF."""

    def __init__(
        self,
        db: DatabaseConnectionManager,
        keyword_engine: Optional[KeywordSearchEngine] = _DEFAULT_KW,
        semantic_engine: Optional[SemanticSearchEngine] = None,
        use_concurrency: bool = True,
    ) -> None:
        self.db = db
        if keyword_engine is _DEFAULT_KW:
            self.keyword_engine = KeywordSearchEngine(db=db)
        else:
            self.keyword_engine = keyword_engine
        self.semantic_engine = semantic_engine
        self.use_concurrency = use_concurrency

    def search(
        self,
        query: Union[str, HybridSearchQuery],
        filters: Optional[SearchFilter] = None,
        limit: int = 20,
        offset: int = 0,
        rrf_k: int = 60,
        candidate_multiplier: int = 5,
        min_similarity: float = -1.0,
    ) -> HybridSearchResponse:
        """Execute a unified hybrid search query combining keyword and semantic candidate pools.

        Args:
            query: Raw query string or structured HybridSearchQuery model.
            filters: Optional search filters (file_types, folder_ids, etc.).
            limit: Maximum number of fused results to return.
            offset: Pagination offset.
            rrf_k: Reciprocal Rank Fusion smoothing constant (default: 60).
            candidate_multiplier: Multiplier for retrieving candidate pools (default: 5).
            min_similarity: Minimum cosine similarity threshold for semantic candidates.

        Returns:
            HybridSearchResponse containing deduplicated, RRF-ranked results.
        """
        start_time = time.perf_counter()

        # 1. Normalize request
        if isinstance(query, HybridSearchQuery):
            search_req = query
        else:
            search_req = HybridSearchQuery(
                query=query,
                filter=filters,
                limit=limit,
                offset=offset,
                rrf_k=rrf_k,
                candidate_multiplier=candidate_multiplier,
                min_similarity=min_similarity,
            )

        clean_query = search_req.query.strip()
        if not clean_query:
            return HybridSearchResponse(
                query=search_req.query,
                total_results=0,
                results=[],
                limit=search_req.limit,
                offset=search_req.offset,
                execution_time_ms=0.0,
                search_mode="hybrid",
                keyword_available=self.keyword_engine is not None,
                semantic_available=self.semantic_engine is not None,
                rrf_k=search_req.rrf_k,
            )

        # 2. Determine candidate pool size
        candidate_limit = min(
            max((search_req.limit + search_req.offset) * search_req.candidate_multiplier, 50),
            500,
        )

        # 3. Retrieve candidates from both engines
        keyword_results: List[SearchResultItem] = []
        semantic_results: List[SemanticSearchResultItem] = []
        kw_available = self.keyword_engine is not None
        sem_available = self.semantic_engine is not None
        fallback_reason: Optional[str] = None
        sem_error: Optional[str] = None
        kw_error: Optional[str] = None

        def run_keyword() -> List[SearchResultItem]:
            if not self.keyword_engine:
                return []
            res = self.keyword_engine.search(
                query=clean_query,
                filters=search_req.filter,
                limit=candidate_limit,
                offset=0,
            )
            return res.results

        def run_semantic() -> List[SemanticSearchResultItem]:
            if not self.semantic_engine:
                return []
            res = self.semantic_engine.search(
                query=clean_query,
                filters=search_req.filter,
                limit=candidate_limit,
                offset=0,
                min_similarity=search_req.min_similarity,
            )
            return res.results

        # Execute candidate searches (concurrently when requested and safe)
        if self.use_concurrency and kw_available and sem_available:
            with ThreadPoolExecutor(max_workers=2) as executor:
                kw_future = executor.submit(self._safe_execute_kw, run_keyword)
                sem_future = executor.submit(self._safe_execute_sem, run_semantic)
                keyword_results, kw_ok, kw_error = kw_future.result()
                semantic_results, sem_ok, sem_error = sem_future.result()
                if not kw_ok:
                    kw_available = False
                if not sem_ok:
                    sem_available = False
        else:
            if kw_available:
                keyword_results, kw_ok, kw_error = self._safe_execute_kw(run_keyword)
                if not kw_ok:
                    kw_available = False
            if sem_available:
                semantic_results, sem_ok, sem_error = self._safe_execute_sem(run_semantic)
                if not sem_ok:
                    sem_available = False

        # 4. Determine actual search mode
        if not kw_available and not sem_available:
            logger.error("Both keyword and semantic search engines are unavailable.")
            duration_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
            fallback_msg = f"both_unavailable: kw={kw_error}, sem={sem_error}"
            return HybridSearchResponse(
                query=search_req.query,
                total_results=0,
                results=[],
                limit=search_req.limit,
                offset=search_req.offset,
                execution_time_ms=duration_ms,
                search_mode="unavailable",
                keyword_available=False,
                semantic_available=False,
                rrf_k=search_req.rrf_k,
                fallback_reason=fallback_msg,
            )

        if kw_available and sem_available:
            if keyword_results and semantic_results:
                search_mode = "hybrid"
            elif keyword_results and not semantic_results:
                search_mode = "keyword_only"
                fallback_reason = None
            elif semantic_results and not keyword_results:
                search_mode = "semantic_only"
                fallback_reason = None
            else:
                search_mode = "hybrid"
        elif kw_available and not sem_available:
            search_mode = "keyword_only"
            fallback_reason = f"semantic_unavailable: {sem_error}" if sem_error else "semantic_engine_unavailable"
        else:
            search_mode = "semantic_only"
            fallback_reason = f"keyword_unavailable: {kw_error}" if kw_error else "keyword_engine_unavailable"

        # 5. Fuse candidate rankings using Reciprocal Rank Fusion
        fused_candidates: List[FusedCandidate] = ReciprocalRankFusion.fuse(
            keyword_items=keyword_results,
            semantic_items=semantic_results,
            k=search_req.rrf_k,
        )

        # 6. Map fused candidates to unified HybridSearchResultItems
        unified_results: List[HybridSearchResultItem] = []
        for cand in fused_candidates:
            primary_item = cand.keyword_item or cand.semantic_item
            if primary_item is None:
                continue

            # Highlights: prefer keyword highlighted terms
            highlights = getattr(cand.keyword_item, "highlights", []) if cand.keyword_item else []
            # Snippet: prefer keyword snippet if it has match highlights, else fallback
            snippet = cand.keyword_item.snippet if cand.keyword_item else cand.semantic_item.snippet

            bm25_score = getattr(cand.keyword_item, "score", None) if cand.keyword_item else None
            cosine_sim = getattr(cand.semantic_item, "cosine_similarity", None) if cand.semantic_item else None
            sem_score = getattr(cand.semantic_item, "score", None) if cand.semantic_item else None

            item = HybridSearchResultItem(
                chunk_id=cand.chunk_id,
                file_id=primary_item.file_id,
                filename=primary_item.filename,
                file_path=primary_item.file_path,
                file_type=primary_item.file_type,
                content_type=getattr(primary_item, "content_type", None),
                file_status=primary_item.file_status,
                is_stale=getattr(primary_item, "is_stale", False),
                chunk_index=primary_item.chunk_index,
                content=primary_item.content,
                snippet=snippet,
                highlights=highlights,
                page_number=primary_item.page_number,
                slide_number=primary_item.slide_number,
                sheet_name=primary_item.sheet_name,
                row_number=primary_item.row_number,
                start_line=primary_item.start_line,
                end_line=primary_item.end_line,
                metadata=primary_item.metadata or {},
                media_metadata=getattr(primary_item, "media_metadata", None),
                embedding_source=getattr(cand.semantic_item, "embedding_source", getattr(primary_item, "embedding_source", None)),
                rrf_score=cand.rrf_score,
                keyword_rank=cand.keyword_rank,
                semantic_rank=cand.semantic_rank,
                bm25_score=bm25_score,
                cosine_similarity=cosine_sim,
                semantic_score=sem_score,
            )
            unified_results.append(item)

        total_matching = len(unified_results)
        paginated_results = unified_results[search_req.offset : search_req.offset + search_req.limit]

        duration_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
        logger.info(
            "Hybrid search for '%s' returned %d results in %.2fms (mode: %s, total candidates: %d)",
            clean_query,
            len(paginated_results),
            duration_ms,
            search_mode,
            total_matching,
        )

        return HybridSearchResponse(
            query=search_req.query,
            total_results=total_matching,
            results=paginated_results,
            limit=search_req.limit,
            offset=search_req.offset,
            execution_time_ms=duration_ms,
            search_mode=search_mode,
            keyword_available=kw_available,
            semantic_available=sem_available,
            rrf_k=search_req.rrf_k,
            fallback_reason=fallback_reason,
        )

    def _safe_execute_kw(self, runner) -> tuple[List[SearchResultItem], bool, Optional[str]]:
        """Safely execute keyword search runner with error capture."""
        try:
            return runner(), True, None
        except Exception as exc:
            logger.warning("Keyword search failed during hybrid query execution: %s", exc)
            return [], False, str(exc)

    def _safe_execute_sem(self, runner) -> tuple[List[SemanticSearchResultItem], bool, Optional[str]]:
        """Safely execute semantic search runner with error capture."""
        try:
            return runner(), True, None
        except Exception as exc:
            logger.warning("Semantic search failed during hybrid query execution: %s", exc)
            return [], False, str(exc)
