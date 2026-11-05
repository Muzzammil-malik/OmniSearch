"""Search application service providing a unified interface across search modes."""

import time
from typing import List, Optional, Union

from app.core.exceptions import SearchExecutionError
from app.core.logging import get_logger
from app.schemas.search import (
    HybridSearchResultItem,
    SearchFilter,
    SearchModeEnum,
    UnifiedSearchQuery,
    UnifiedSearchResponse,
)
from app.search.hybrid_search import HybridSearchEngine
from app.search.keyword_search import KeywordSearchEngine
from app.search.semantic_search import SemanticSearchEngine

logger = get_logger(__name__)


class SearchService:
    """Orchestrates keyword, semantic, and hybrid search pipelines through a unified API."""

    def __init__(
        self,
        keyword_engine: Optional[KeywordSearchEngine] = None,
        semantic_engine: Optional[SemanticSearchEngine] = None,
        hybrid_engine: Optional[HybridSearchEngine] = None,
    ) -> None:
        self.keyword_engine = keyword_engine
        self.semantic_engine = semantic_engine
        self.hybrid_engine = hybrid_engine

    def search(
        self,
        query: Union[str, UnifiedSearchQuery],
        mode: SearchModeEnum = SearchModeEnum.HYBRID,
        filters: Optional[SearchFilter] = None,
        limit: int = 20,
        offset: int = 0,
        rrf_k: int = 60,
        candidate_multiplier: int = 5,
        min_similarity: float = -1.0,
    ) -> UnifiedSearchResponse:
        """Execute search under requested strategy and normalize to unified response contract."""
        start_time = time.perf_counter()

        if isinstance(query, UnifiedSearchQuery):
            req = query
        else:
            req = UnifiedSearchQuery(
                query=query,
                mode=mode,
                filter=filters,
                limit=limit,
                offset=offset,
                rrf_k=rrf_k,
                candidate_multiplier=candidate_multiplier,
                min_similarity=min_similarity,
            )

        clean_query = req.query.strip()
        if not clean_query:
            return UnifiedSearchResponse(
                query=req.query,
                requested_mode=req.mode,
                effective_mode=req.mode.value,
                total_results=0,
                results=[],
                limit=req.limit,
                offset=req.offset,
                execution_time_ms=0.0,
                keyword_available=self.keyword_engine is not None,
                semantic_available=self.semantic_engine is not None,
                rrf_k=req.rrf_k,
            )

        try:
            if req.mode == SearchModeEnum.KEYWORD:
                return self._search_keyword(req, clean_query, start_time)
            elif req.mode == SearchModeEnum.SEMANTIC:
                return self._search_semantic(req, clean_query, start_time)
            else:
                return self._search_hybrid(req, clean_query, start_time)
        except Exception as exc:
            logger.error("Search failed for query '%s' in mode '%s': %s", clean_query, req.mode.value, exc, exc_info=True)
            raise SearchExecutionError(clean_query, str(exc))

    def _search_keyword(
        self, req: UnifiedSearchQuery, clean_query: str, start_time: float
    ) -> UnifiedSearchResponse:
        if not self.keyword_engine:
            duration_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
            return UnifiedSearchResponse(
                query=req.query,
                requested_mode=req.mode,
                effective_mode="unavailable",
                total_results=0,
                results=[],
                limit=req.limit,
                offset=req.offset,
                execution_time_ms=duration_ms,
                keyword_available=False,
                semantic_available=self.semantic_engine is not None,
                rrf_k=req.rrf_k,
            )

        res = self.keyword_engine.search(
            query=clean_query,
            filters=req.filter,
            limit=req.limit,
            offset=req.offset,
        )

        unified_results: List[HybridSearchResultItem] = []
        for idx, item in enumerate(res.results, start=1 + req.offset):
            unified_results.append(
                HybridSearchResultItem(
                    chunk_id=item.chunk_id,
                    file_id=item.file_id,
                    filename=item.filename,
                    file_path=item.file_path,
                    file_type=item.file_type,
                    file_status=item.file_status,
                    is_stale=getattr(item, "is_stale", False),
                    chunk_index=item.chunk_index,
                    content=item.content,
                    snippet=item.snippet,
                    highlights=item.highlights,
                    page_number=item.page_number,
                    slide_number=item.slide_number,
                    sheet_name=item.sheet_name,
                    row_number=item.row_number,
                    start_line=item.start_line,
                    end_line=item.end_line,
                    metadata=item.metadata or {},
                    rrf_score=round(1.0 / (req.rrf_k + idx), 6),
                    keyword_rank=idx,
                    semantic_rank=None,
                    bm25_score=item.score,
                    cosine_similarity=None,
                    semantic_score=None,
                )
            )

        duration_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
        return UnifiedSearchResponse(
            query=req.query,
            requested_mode=req.mode,
            effective_mode="keyword",
            total_results=res.total_results,
            results=unified_results,
            limit=req.limit,
            offset=req.offset,
            execution_time_ms=duration_ms,
            keyword_available=True,
            semantic_available=self.semantic_engine is not None,
            rrf_k=req.rrf_k,
        )

    def _search_semantic(
        self, req: UnifiedSearchQuery, clean_query: str, start_time: float
    ) -> UnifiedSearchResponse:
        if not self.semantic_engine:
            duration_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
            return UnifiedSearchResponse(
                query=req.query,
                requested_mode=req.mode,
                effective_mode="unavailable",
                total_results=0,
                results=[],
                limit=req.limit,
                offset=req.offset,
                execution_time_ms=duration_ms,
                keyword_available=self.keyword_engine is not None,
                semantic_available=False,
                rrf_k=req.rrf_k,
            )

        res = self.semantic_engine.search(
            query=clean_query,
            filters=req.filter,
            limit=req.limit,
            offset=req.offset,
            min_similarity=req.min_similarity,
        )

        unified_results: List[HybridSearchResultItem] = []
        for idx, item in enumerate(res.results, start=1 + req.offset):
            unified_results.append(
                HybridSearchResultItem(
                    chunk_id=item.chunk_id,
                    file_id=item.file_id,
                    filename=item.filename,
                    file_path=item.file_path,
                    file_type=item.file_type,
                    file_status=item.file_status,
                    is_stale=getattr(item, "is_stale", False),
                    chunk_index=item.chunk_index,
                    content=item.content,
                    snippet=item.snippet,
                    highlights=[],
                    page_number=item.page_number,
                    slide_number=item.slide_number,
                    sheet_name=item.sheet_name,
                    row_number=item.row_number,
                    start_line=item.start_line,
                    end_line=item.end_line,
                    metadata=item.metadata or {},
                    rrf_score=round(1.0 / (req.rrf_k + idx), 6),
                    keyword_rank=None,
                    semantic_rank=idx,
                    bm25_score=None,
                    cosine_similarity=item.cosine_similarity,
                    semantic_score=item.score,
                )
            )

        duration_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
        return UnifiedSearchResponse(
            query=req.query,
            requested_mode=req.mode,
            effective_mode="semantic",
            total_results=res.total_results,
            results=unified_results,
            limit=req.limit,
            offset=req.offset,
            execution_time_ms=duration_ms,
            keyword_available=self.keyword_engine is not None,
            semantic_available=True,
            rrf_k=req.rrf_k,
        )

    def _search_hybrid(
        self, req: UnifiedSearchQuery, clean_query: str, start_time: float
    ) -> UnifiedSearchResponse:
        if not self.hybrid_engine:
            duration_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
            return UnifiedSearchResponse(
                query=req.query,
                requested_mode=req.mode,
                effective_mode="unavailable",
                total_results=0,
                results=[],
                limit=req.limit,
                offset=req.offset,
                execution_time_ms=duration_ms,
                keyword_available=self.keyword_engine is not None,
                semantic_available=self.semantic_engine is not None,
                rrf_k=req.rrf_k,
            )

        res = self.hybrid_engine.search(
            query=clean_query,
            filters=req.filter,
            limit=req.limit,
            offset=req.offset,
            rrf_k=req.rrf_k,
            candidate_multiplier=req.candidate_multiplier,
            min_similarity=req.min_similarity,
        )

        return UnifiedSearchResponse(
            query=req.query,
            requested_mode=req.mode,
            effective_mode=res.search_mode,
            total_results=res.total_results,
            results=res.results,
            limit=req.limit,
            offset=req.offset,
            execution_time_ms=res.execution_time_ms,
            keyword_available=res.keyword_available,
            semantic_available=res.semantic_available,
            rrf_k=res.rrf_k,
        )

