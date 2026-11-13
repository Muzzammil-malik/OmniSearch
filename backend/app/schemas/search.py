"""Pydantic schemas for keyword search requests, filters, results, and responses."""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, model_validator


class SearchFilter(BaseModel):
    """Filtering criteria for narrowing keyword search results."""

    file_types: Optional[List[str]] = Field(
        default=None,
        description="Filter by specific file types (e.g. ['pdf', 'docx', 'code']).",
    )
    folder_ids: Optional[List[int]] = Field(
        default=None,
        description="Filter by indexed folder database IDs.",
    )
    folder_id: Optional[int] = Field(
        default=None,
        description="Filter by a single indexed folder database ID.",
    )
    library_folder_id: Optional[int] = Field(
        default=None,
        description="Alias for single library folder database ID.",
    )
    folder_paths: Optional[List[str]] = Field(
        default=None,
        description="Filter by root folder file paths.",
    )
    max_chunks_per_file: Optional[int] = Field(
        default=3,
        ge=1,
        le=50,
        description="Maximum matching chunks to return per file (prevents single-document dominance).",
    )

    def get_effective_folder_ids(self) -> Optional[List[int]]:
        """Return combined, deduplicated list of folder IDs from folder_ids, folder_id, and library_folder_id."""
        ids: List[int] = []
        if self.folder_ids:
            ids.extend(self.folder_ids)
        if self.folder_id is not None:
            ids.append(self.folder_id)
        if self.library_folder_id is not None:
            ids.append(self.library_folder_id)
        if not ids:
            return None
        return list(dict.fromkeys(ids))


class SearchQuery(BaseModel):
    """Incoming keyword search query request."""

    query: str = Field(..., min_length=1, description="Raw keyword or phrase search query.")
    filter: Optional[SearchFilter] = Field(default=None, description="Optional search filters.")
    library_folder_id: Optional[int] = Field(
        default=None,
        description="Optional library folder database ID for scoping searches.",
    )
    folder_id: Optional[int] = Field(
        default=None,
        description="Alias for library_folder_id.",
    )
    limit: int = Field(default=20, ge=1, le=100, description="Maximum number of results to return.")
    offset: int = Field(default=0, ge=0, description="Offset for pagination.")

    @model_validator(mode="after")
    def sync_folder_scope(self) -> "SearchQuery":
        fid = self.library_folder_id if self.library_folder_id is not None else self.folder_id
        if fid is not None:
            if self.filter is None:
                self.filter = SearchFilter(folder_ids=[fid])
            else:
                effective = self.filter.get_effective_folder_ids() or []
                if fid not in effective:
                    effective.append(fid)
                self.filter.folder_ids = effective
        elif self.filter is not None:
            effective = self.filter.get_effective_folder_ids()
            if effective:
                self.filter.folder_ids = effective
        return self


class SearchResultItem(BaseModel):
    """Individual document chunk keyword search match with structural metadata and snippet."""

    file_id: int
    chunk_id: int
    filename: str
    file_path: str
    file_type: str
    content_type: Optional[str] = Field(
        default=None,
        description="Top-level modality content type ('document', 'image', 'audio', 'video').",
    )
    file_status: str
    is_stale: bool = Field(
        default=False,
        description="True if previously indexed content was retained after a subsequent re-indexing error.",
    )
    chunk_index: int
    content: str
    snippet: str = Field(..., description="Contextual snippet with highlighted match terms.")
    highlights: List[str] = Field(
        default_factory=list,
        description="Exact terms or phrases matching the search query.",
    )
    page_number: Optional[int] = None
    slide_number: Optional[int] = None
    sheet_name: Optional[str] = None
    row_number: Optional[int] = None
    start_line: Optional[int] = None
    end_line: Optional[int] = None
    score: float = Field(..., description="Normalized positive relevance score (higher is better).")
    bm25_rank: float = Field(..., description="Raw SQLite FTS5 BM25 rank score (negative value; lower is better).")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Custom chunk metadata.")
    media_metadata: Optional[Dict[str, Any]] = Field(default=None, description="Media attributes (duration, resolution, etc.).")
    embedding_source: Optional[str] = Field(
        default=None,
        description="Origin of embedding representation ('native_multimodal', 'metadata_fallback', or 'text').",
    )


class SearchResponse(BaseModel):
    """Structured keyword search response returned to clients."""

    query: str
    total_results: int
    results: List[SearchResultItem]
    limit: int
    offset: int
    execution_time_ms: float


class SemanticSearchQuery(BaseModel):
    """Incoming semantic search query request."""

    query: str = Field(..., min_length=1, description="Natural language semantic search query.")
    filter: Optional[SearchFilter] = Field(default=None, description="Optional search filters.")
    library_folder_id: Optional[int] = Field(
        default=None,
        description="Optional library folder database ID for scoping searches.",
    )
    folder_id: Optional[int] = Field(
        default=None,
        description="Alias for library_folder_id.",
    )
    limit: int = Field(default=20, ge=1, le=100, description="Maximum number of results to return.")
    offset: int = Field(default=0, ge=0, description="Offset for pagination.")
    min_similarity: float = Field(
        default=-1.0,
        ge=-1.0,
        le=1.0,
        description="Minimum cosine similarity threshold.",
    )

    @model_validator(mode="after")
    def sync_folder_scope(self) -> "SemanticSearchQuery":
        fid = self.library_folder_id if self.library_folder_id is not None else self.folder_id
        if fid is not None:
            if self.filter is None:
                self.filter = SearchFilter(folder_ids=[fid])
            else:
                effective = self.filter.get_effective_folder_ids() or []
                if fid not in effective:
                    effective.append(fid)
                self.filter.folder_ids = effective
        elif self.filter is not None:
            effective = self.filter.get_effective_folder_ids()
            if effective:
                self.filter.folder_ids = effective
        return self


class SemanticSearchResultItem(BaseModel):
    """Individual document chunk match from semantic vector search."""

    file_id: int
    chunk_id: int
    filename: str
    file_path: str
    file_type: str
    content_type: Optional[str] = Field(
        default=None,
        description="Top-level modality content type ('document', 'image', 'audio', 'video').",
    )
    file_status: str
    is_stale: bool = Field(
        default=False,
        description="True if previously indexed content was retained after a subsequent re-indexing error.",
    )
    chunk_index: int
    content: str
    snippet: str = Field(..., description="Contextual text snippet from the chunk.")
    score: float = Field(..., description="Normalized relevance score [0.0, 1.0] (higher is better).")
    cosine_similarity: float = Field(..., description="Cosine similarity score in range [-1.0, 1.0].")
    distance: float = Field(..., description="Raw cosine distance in range [0.0, 2.0].")
    page_number: Optional[int] = None
    slide_number: Optional[int] = None
    sheet_name: Optional[str] = None
    row_number: Optional[int] = None
    start_line: Optional[int] = None
    end_line: Optional[int] = None
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Custom chunk metadata.")
    media_metadata: Optional[Dict[str, Any]] = Field(default=None, description="Media attributes (duration, resolution, etc.).")
    embedding_source: Optional[str] = Field(
        default=None,
        description="Origin of embedding representation ('native_multimodal', 'metadata_fallback', or 'text').",
    )


class SemanticSearchResponse(BaseModel):
    """Structured semantic search response returned to clients."""

    query: str
    total_results: int
    results: List[SemanticSearchResultItem]
    limit: int
    offset: int
    execution_time_ms: float
    model_id: str


class HybridSearchQuery(BaseModel):
    """Incoming hybrid search query combining keyword and semantic parameters."""

    query: str = Field(..., min_length=1, description="Raw keyword or natural language query.")
    filter: Optional[SearchFilter] = Field(default=None, description="Optional search filters.")
    library_folder_id: Optional[int] = Field(
        default=None,
        description="Optional library folder database ID for scoping searches.",
    )
    folder_id: Optional[int] = Field(
        default=None,
        description="Alias for library_folder_id.",
    )
    limit: int = Field(default=20, ge=1, le=100, description="Maximum number of unified results to return.")
    offset: int = Field(default=0, ge=0, description="Offset for pagination.")
    rrf_k: int = Field(
        default=60,
        ge=1,
        le=1000,
        description="Reciprocal Rank Fusion smoothing constant k (default: 60).",
    )
    candidate_multiplier: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Candidate pool multiplier per engine before RRF fusion (default: 5).",
    )
    min_similarity: float = Field(
        default=-1.0,
        ge=-1.0,
        le=1.0,
        description="Minimum cosine similarity threshold for semantic candidates.",
    )

    @model_validator(mode="after")
    def sync_folder_scope(self) -> "HybridSearchQuery":
        fid = self.library_folder_id if self.library_folder_id is not None else self.folder_id
        if fid is not None:
            if self.filter is None:
                self.filter = SearchFilter(folder_ids=[fid])
            else:
                effective = self.filter.get_effective_folder_ids() or []
                if fid not in effective:
                    effective.append(fid)
                self.filter.folder_ids = effective
        elif self.filter is not None:
            effective = self.filter.get_effective_folder_ids()
            if effective:
                self.filter.folder_ids = effective
        return self


class HybridSearchResultItem(BaseModel):
    """Unified document chunk match fused from lexical and semantic search engines."""

    chunk_id: int
    file_id: int
    filename: str
    file_path: str
    file_type: str
    content_type: Optional[str] = Field(
        default=None,
        description="Top-level modality content type ('document', 'image', 'audio', 'video').",
    )
    file_status: str
    is_stale: bool = Field(
        default=False,
        description="True if previously indexed content was retained after a subsequent re-indexing error.",
    )
    chunk_index: int
    content: str
    snippet: str = Field(..., description="Contextual snippet of the chunk.")
    highlights: List[str] = Field(
        default_factory=list,
        description="Extracted matched keywords or phrases.",
    )
    page_number: Optional[int] = None
    slide_number: Optional[int] = None
    sheet_name: Optional[str] = None
    row_number: Optional[int] = None
    start_line: Optional[int] = None
    end_line: Optional[int] = None
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Custom chunk metadata.")
    media_metadata: Optional[Dict[str, Any]] = Field(default=None, description="Media attributes (duration, resolution, etc.).")
    embedding_source: Optional[str] = Field(
        default=None,
        description="Origin of embedding representation ('native_multimodal', 'metadata_fallback', or 'text').",
    )

    # Reciprocal Rank Fusion & Underlying Metrics
    rrf_score: float = Field(..., description="Combined Reciprocal Rank Fusion score (primary sort).")
    keyword_rank: Optional[int] = Field(
        default=None,
        description="1-based rank within keyword search candidate pool (None if not in keyword pool).",
    )
    semantic_rank: Optional[int] = Field(
        default=None,
        description="1-based rank within semantic search candidate pool (None if not in semantic pool).",
    )
    bm25_score: Optional[float] = Field(
        default=None,
        description="Normalized BM25 score from keyword search if available.",
    )
    cosine_similarity: Optional[float] = Field(
        default=None,
        description="Raw cosine similarity score from vector search if available.",
    )
    semantic_score: Optional[float] = Field(
        default=None,
        description="Normalized semantic similarity score in [0.0, 1.0] if available.",
    )


class HybridSearchResponse(BaseModel):
    """Structured hybrid search response returned to clients."""

    query: str
    total_results: int
    results: List[HybridSearchResultItem]
    limit: int
    offset: int
    execution_time_ms: float
    search_mode: str = Field(
        ...,
        description="Execution mode: 'hybrid', 'keyword_only', 'semantic_only'.",
    )
    keyword_available: bool = Field(
        ...,
        description="True if keyword search engine was operational during query execution.",
    )
    semantic_available: bool = Field(
        ...,
        description="True if semantic search engine was operational during query execution.",
    )
    rrf_k: int = Field(
        default=60,
        description="RRF smoothing constant k used during ranking fusion.",
    )
    fallback_reason: Optional[str] = Field(
        default=None,
        description="Reason for search engine fallback or degradation (e.g. semantic engine unavailable).",
    )


class SearchModeEnum(str, Enum):
    """User-selectable search strategy."""

    HYBRID = "hybrid"
    KEYWORD = "keyword"
    SEMANTIC = "semantic"


class UnifiedSearchQuery(BaseModel):
    """Unified application search request supporting hybrid, keyword, and semantic modes."""

    query: str = Field(..., min_length=1, description="Search query string.")
    mode: SearchModeEnum = Field(
        default=SearchModeEnum.HYBRID,
        description="Search execution mode: 'hybrid', 'keyword', or 'semantic'.",
    )
    filter: Optional[SearchFilter] = Field(default=None, description="Optional search filters.")
    library_folder_id: Optional[int] = Field(
        default=None,
        description="Optional library folder database ID for scoping searches.",
    )
    folder_id: Optional[int] = Field(
        default=None,
        description="Alias for library_folder_id.",
    )
    limit: int = Field(default=20, ge=1, le=100, description="Maximum number of results to return.")
    offset: int = Field(default=0, ge=0, description="Offset for pagination.")
    rrf_k: int = Field(default=60, ge=1, le=1000, description="RRF smoothing constant k (for hybrid mode).")
    candidate_multiplier: int = Field(default=5, ge=1, le=20, description="Candidate multiplier (for hybrid mode).")
    min_similarity: float = Field(default=-1.0, ge=-1.0, le=1.0, description="Min cosine similarity (for semantic mode).")

    @model_validator(mode="after")
    def sync_folder_scope(self) -> "UnifiedSearchQuery":
        fid = self.library_folder_id if self.library_folder_id is not None else self.folder_id
        if fid is not None:
            if self.filter is None:
                self.filter = SearchFilter(folder_ids=[fid])
            else:
                effective = self.filter.get_effective_folder_ids() or []
                if fid not in effective:
                    effective.append(fid)
                self.filter.folder_ids = effective
        elif self.filter is not None:
            effective = self.filter.get_effective_folder_ids()
            if effective:
                self.filter.folder_ids = effective
        return self


class UnifiedSearchResponse(BaseModel):
    """Unified search response model presenting standard results across all modes."""

    query: str
    requested_mode: SearchModeEnum
    effective_mode: str = Field(
        ...,
        description="Effective execution mode: 'hybrid', 'keyword', 'semantic', 'keyword_only', 'semantic_only', 'unavailable'.",
    )
    total_results: int
    results: List[HybridSearchResultItem]
    limit: int
    offset: int
    execution_time_ms: float
    keyword_available: bool = True
    semantic_available: bool = True
    rrf_k: Optional[int] = 60
