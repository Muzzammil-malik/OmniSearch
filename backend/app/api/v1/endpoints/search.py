"""Search API endpoints for executing FTS5 keyword, ChromaDB semantic, RRF hybrid, and unified searches."""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query

from app.core.config import get_settings
from app.database.connection import DatabaseConnectionManager
from app.embeddings.configuration import EmbeddingConfig
from app.embeddings.embedder import EmbeddingGemmaEmbedder
from app.schemas.search import (
    HybridSearchQuery,
    HybridSearchResponse,
    SearchFilter,
    SearchModeEnum,
    SearchQuery,
    SearchResponse,
    SemanticSearchQuery,
    SemanticSearchResponse,
    UnifiedSearchQuery,
    UnifiedSearchResponse,
)
from app.search.hybrid_search import HybridSearchEngine
from app.search.keyword_search import KeywordSearchEngine
from app.search.semantic_search import SemanticSearchEngine
from app.services.search_service import SearchService
from app.vector_store.chroma import ChromaVectorStore

router = APIRouter()


def get_search_engine() -> KeywordSearchEngine:
    """Dependency providing a configured KeywordSearchEngine instance."""
    db = DatabaseConnectionManager()
    return KeywordSearchEngine(db=db)


def get_semantic_search_engine() -> SemanticSearchEngine:
    """Dependency providing a configured SemanticSearchEngine instance."""
    db = DatabaseConnectionManager()
    settings = get_settings()
    vector_store = ChromaVectorStore(persist_dir=settings.vectors_dir)
    resolved_model = settings.resolved_embedding_model
    config = EmbeddingConfig(
        model_id=resolved_model,
        dimension=settings.embedding_dimension,
        batch_size=settings.embedding_batch_size,
        device=settings.embedding_device,
        precision=settings.embedding_precision,
        local_files_only=(resolved_model != settings.embedding_model_id),
    )
    embedder = EmbeddingGemmaEmbedder(config=config)
    return SemanticSearchEngine(db=db, vector_store=vector_store, embedder=embedder)


def get_hybrid_search_engine(
    keyword_engine: KeywordSearchEngine = Depends(get_search_engine),
    semantic_engine: SemanticSearchEngine = Depends(get_semantic_search_engine),
) -> HybridSearchEngine:
    """Dependency providing a configured HybridSearchEngine instance."""
    db = DatabaseConnectionManager()
    return HybridSearchEngine(
        db=db,
        keyword_engine=keyword_engine,
        semantic_engine=semantic_engine,
    )


def get_search_service(
    keyword_engine: KeywordSearchEngine = Depends(get_search_engine),
    semantic_engine: SemanticSearchEngine = Depends(get_semantic_search_engine),
    hybrid_engine: HybridSearchEngine = Depends(get_hybrid_search_engine),
) -> SearchService:
    """Dependency providing a configured SearchService instance."""
    return SearchService(
        keyword_engine=keyword_engine,
        semantic_engine=semantic_engine,
        hybrid_engine=hybrid_engine,
    )


@router.post(
    "/search",
    response_model=SearchResponse,
    summary="Execute Keyword Search",
    description="Search indexed documents using SQLite FTS5, BM25 ranking, and metadata filters.",
)
async def execute_search(
    request: SearchQuery,
    engine: KeywordSearchEngine = Depends(get_search_engine),
) -> SearchResponse:
    """Execute keyword search using structured search request model."""
    return engine.search(request)


@router.get(
    "/search",
    response_model=SearchResponse,
    summary="Execute Keyword Search (GET)",
    description="Search indexed documents using query parameters for simple keyword lookups.",
)
async def search_get(
    q: str = Query(..., min_length=1, description="Keyword or phrase query"),
    limit: int = Query(default=20, ge=1, le=100, description="Max results to return"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
    file_type: Optional[List[str]] = Query(default=None, description="Optional file type filter(s)"),
    library_folder_id: Optional[int] = Query(default=None, description="Optional library folder ID to scope search"),
    folder_id: Optional[int] = Query(default=None, description="Alias for library_folder_id"),
    max_chunks_per_file: int = Query(default=3, ge=1, le=50, description="Max chunks per file"),
    engine: KeywordSearchEngine = Depends(get_search_engine),
) -> SearchResponse:
    """Execute keyword search via GET query parameters."""
    scoped_id = library_folder_id if library_folder_id is not None else folder_id
    filters = SearchFilter(
        file_types=file_type,
        folder_ids=[scoped_id] if scoped_id is not None else None,
        max_chunks_per_file=max_chunks_per_file,
    )
    search_req = SearchQuery(
        query=q,
        filter=filters,
        library_folder_id=scoped_id,
        limit=limit,
        offset=offset,
    )
    return engine.search(search_req)


@router.post(
    "/search/semantic",
    response_model=SemanticSearchResponse,
    summary="Execute Semantic Search",
    description="Search indexed documents using dense vector similarity retrieval powered by ChromaDB.",
)
async def execute_semantic_search(
    request: SemanticSearchQuery,
    engine: SemanticSearchEngine = Depends(get_semantic_search_engine),
) -> SemanticSearchResponse:
    """Execute semantic vector search using structured request model."""
    return engine.search(request)


@router.get(
    "/search/semantic",
    response_model=SemanticSearchResponse,
    summary="Execute Semantic Search (GET)",
    description="Search indexed documents using natural language query parameters via ChromaDB.",
)
async def semantic_search_get(
    q: str = Query(..., min_length=1, description="Natural language semantic search query"),
    limit: int = Query(default=20, ge=1, le=100, description="Max results to return"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
    min_similarity: float = Query(
        default=-1.0, ge=-1.0, le=1.0, description="Minimum cosine similarity threshold"
    ),
    file_type: Optional[List[str]] = Query(default=None, description="Optional file type filter(s)"),
    library_folder_id: Optional[int] = Query(default=None, description="Optional library folder ID to scope search"),
    folder_id: Optional[int] = Query(default=None, description="Alias for library_folder_id"),
    max_chunks_per_file: int = Query(default=3, ge=1, le=50, description="Max chunks per file"),
    engine: SemanticSearchEngine = Depends(get_semantic_search_engine),
) -> SemanticSearchResponse:
    """Execute semantic vector search via GET query parameters."""
    scoped_id = library_folder_id if library_folder_id is not None else folder_id
    filters = SearchFilter(
        file_types=file_type,
        folder_ids=[scoped_id] if scoped_id is not None else None,
        max_chunks_per_file=max_chunks_per_file,
    )
    search_req = SemanticSearchQuery(
        query=q,
        filter=filters,
        library_folder_id=scoped_id,
        limit=limit,
        offset=offset,
        min_similarity=min_similarity,
    )
    return engine.search(search_req)


@router.post(
    "/search/hybrid",
    response_model=HybridSearchResponse,
    summary="Execute Hybrid Search",
    description="Search indexed documents combining SQLite FTS5 lexical matching and ChromaDB semantic similarity via Reciprocal Rank Fusion (RRF).",
)
async def execute_hybrid_search(
    request: HybridSearchQuery,
    engine: HybridSearchEngine = Depends(get_hybrid_search_engine),
) -> HybridSearchResponse:
    """Execute hybrid search using structured request model."""
    return engine.search(request)


@router.get(
    "/search/hybrid",
    response_model=HybridSearchResponse,
    summary="Execute Hybrid Search (GET)",
    description="Search indexed documents combining keyword and vector results via GET query parameters.",
)
async def hybrid_search_get(
    q: str = Query(..., min_length=1, description="Search query string"),
    limit: int = Query(default=20, ge=1, le=100, description="Max results to return"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
    rrf_k: int = Query(default=60, ge=1, le=1000, description="RRF smoothing constant k"),
    candidate_multiplier: int = Query(
        default=5, ge=1, le=20, description="Candidate pool multiplier"
    ),
    min_similarity: float = Query(
        default=-1.0, ge=-1.0, le=1.0, description="Minimum cosine similarity for semantic candidates"
    ),
    file_type: Optional[List[str]] = Query(default=None, description="Optional file type filter(s)"),
    library_folder_id: Optional[int] = Query(default=None, description="Optional library folder ID to scope search"),
    folder_id: Optional[int] = Query(default=None, description="Alias for library_folder_id"),
    max_chunks_per_file: int = Query(default=3, ge=1, le=50, description="Max chunks per file"),
    engine: HybridSearchEngine = Depends(get_hybrid_search_engine),
) -> HybridSearchResponse:
    """Execute hybrid search via GET query parameters."""
    scoped_id = library_folder_id if library_folder_id is not None else folder_id
    filters = SearchFilter(
        file_types=file_type,
        folder_ids=[scoped_id] if scoped_id is not None else None,
        max_chunks_per_file=max_chunks_per_file,
    )
    search_req = HybridSearchQuery(
        query=q,
        filter=filters,
        library_folder_id=scoped_id,
        limit=limit,
        offset=offset,
        rrf_k=rrf_k,
        candidate_multiplier=candidate_multiplier,
        min_similarity=min_similarity,
    )
    return engine.search(search_req)


@router.post(
    "/search/unified",
    response_model=UnifiedSearchResponse,
    summary="Unified Search (POST)",
    description="Application-facing unified search endpoint supporting hybrid, keyword, and semantic modes.",
)
async def execute_unified_search(
    request: UnifiedSearchQuery,
    service: SearchService = Depends(get_search_service),
) -> UnifiedSearchResponse:
    """Execute unified search across configurable mode strategies."""
    return service.search(request)


@router.get(
    "/search/unified",
    response_model=UnifiedSearchResponse,
    summary="Unified Search (GET)",
    description="Application-facing unified search endpoint via GET query parameters.",
)
async def unified_search_get(
    q: str = Query(..., min_length=1, description="Search query string"),
    mode: SearchModeEnum = Query(default=SearchModeEnum.HYBRID, description="Search mode: hybrid, keyword, semantic"),
    limit: int = Query(default=20, ge=1, le=100, description="Max results to return"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
    rrf_k: int = Query(default=60, ge=1, le=1000, description="RRF smoothing constant k"),
    candidate_multiplier: int = Query(default=5, ge=1, le=20, description="Candidate multiplier"),
    min_similarity: float = Query(default=-1.0, ge=-1.0, le=1.0, description="Min similarity for semantic candidates"),
    file_type: Optional[List[str]] = Query(default=None, description="Optional file type filter(s)"),
    library_folder_id: Optional[int] = Query(default=None, description="Optional library folder ID to scope search"),
    folder_id: Optional[int] = Query(default=None, description="Alias for library_folder_id"),
    max_chunks_per_file: int = Query(default=3, ge=1, le=50, description="Max chunks per file"),
    service: SearchService = Depends(get_search_service),
) -> UnifiedSearchResponse:
    """Execute unified search via GET query parameters."""
    scoped_id = library_folder_id if library_folder_id is not None else folder_id
    filters = SearchFilter(
        file_types=file_type,
        folder_ids=[scoped_id] if scoped_id is not None else None,
        max_chunks_per_file=max_chunks_per_file,
    )
    req = UnifiedSearchQuery(
        query=q,
        mode=mode,
        filter=filters,
        library_folder_id=scoped_id,
        limit=limit,
        offset=offset,
        rrf_k=rrf_k,
        candidate_multiplier=candidate_multiplier,
        min_similarity=min_similarity,
    )
    return service.search(req)
