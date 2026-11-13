"""Pydantic schemas for API request and response data models."""

from app.schemas.health import HealthResponse
from app.schemas.errors import ErrorResponse
from app.schemas.folder import (
    FolderCreateRequest,
    FolderDeleteResponse,
    FolderListResponse,
    FolderResponse,
    FolderUpdateRequest,
)
from app.schemas.indexing import (
    IndexJobResponse,
    IndexTriggerRequest,
    IndexingStatsResponse,
    IndexingStatusResponse,
)
from app.schemas.system import (
    DatabaseStatus,
    EmbeddingModelStatus,
    SystemStatusResponse,
    VectorStoreStatus,
)
from app.schemas.extraction import (
    ExtractedDocument,
    ExtractedSegment,
    ExtractionBatchSummary,
    ExtractionStatus,
    ScanReport,
    ScannedFile,
    SegmentType,
)
from app.schemas.processing import (
    ChunkRecord,
    DocumentChunk,
    FileRecord,
    FolderRecord,
    IndexJobRecord,
    IndexJobStatus,
)
from app.schemas.search import (
    HybridSearchQuery,
    HybridSearchResponse,
    HybridSearchResultItem,
    SearchFilter,
    SearchModeEnum,
    SearchQuery,
    SearchResultItem,
    SearchResponse,
    SemanticSearchQuery,
    SemanticSearchResultItem,
    SemanticSearchResponse,
    UnifiedSearchQuery,
    UnifiedSearchResponse,
)

__all__ = [
    "HealthResponse",
    "ErrorResponse",
    "FolderCreateRequest",
    "FolderUpdateRequest",
    "FolderResponse",
    "FolderListResponse",
    "FolderDeleteResponse",
    "IndexTriggerRequest",
    "IndexJobResponse",
    "IndexingStatusResponse",
    "IndexingStatsResponse",
    "DatabaseStatus",
    "VectorStoreStatus",
    "EmbeddingModelStatus",
    "SystemStatusResponse",
    "ExtractedDocument",
    "ExtractedSegment",
    "ExtractionBatchSummary",
    "ExtractionStatus",
    "ScanReport",
    "ScannedFile",
    "SegmentType",
    "DocumentChunk",
    "FolderRecord",
    "FileRecord",
    "ChunkRecord",
    "IndexJobRecord",
    "IndexJobStatus",
    "SearchFilter",
    "SearchModeEnum",
    "SearchQuery",
    "SearchResultItem",
    "SearchResponse",
    "SemanticSearchQuery",
    "SemanticSearchResultItem",
    "SemanticSearchResponse",
    "HybridSearchQuery",
    "HybridSearchResultItem",
    "HybridSearchResponse",
    "UnifiedSearchQuery",
    "UnifiedSearchResponse",
]
