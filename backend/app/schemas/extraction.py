"""Pydantic schemas for document ingestion and text extraction."""

from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ExtractionStatus(str, Enum):
    """Status outcomes for document extraction."""

    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    EMPTY = "empty"
    UNSUPPORTED = "unsupported"


class SegmentType(str, Enum):
    """Structural type of an extracted content segment."""

    PAGE = "page"
    PARAGRAPH = "paragraph"
    TABLE = "table"
    ROW = "row"
    SLIDE = "slide"
    SHEET = "sheet"
    CODE_BLOCK = "code_block"
    TEXT_BLOCK = "text_block"
    HEADING = "heading"


class ExtractedSegment(BaseModel):
    """A granular segment of extracted document content with location metadata."""

    content: str = Field(..., description="Extracted textual content")
    segment_index: int = Field(..., description="0-indexed position of segment within document")
    segment_type: SegmentType = Field(default=SegmentType.TEXT_BLOCK, description="Semantic segment type")

    # Format-specific location pointers (optional depending on format)
    page_number: Optional[int] = Field(default=None, description="1-indexed page number (PDF)")
    slide_number: Optional[int] = Field(default=None, description="1-indexed slide number (PPTX)")
    sheet_name: Optional[str] = Field(default=None, description="Spreadsheet sheet name (XLSX)")
    row_number: Optional[int] = Field(default=None, description="Row number (CSV, XLSX)")
    start_line: Optional[int] = Field(default=None, description="1-indexed starting line number (Code, Text)")
    end_line: Optional[int] = Field(default=None, description="1-indexed ending line number (Code, Text)")

    # Additional contextual metadata
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Segment-specific metadata attributes")


class ExtractedDocument(BaseModel):
    """Standardized document extraction result across all supported file types."""

    file_path: str = Field(..., description="Absolute normalized path to the source file")
    filename: str = Field(..., description="Filename including extension")
    extension: str = Field(..., description="File extension normalized with leading dot, e.g. .pdf")
    file_type: str = Field(..., description="Categorical format identifier, e.g. pdf, docx, code")
    file_size: int = Field(..., description="File size in bytes")
    sha256: Optional[str] = Field(default=None, description="Cryptographic SHA-256 hex digest of source file")
    extracted_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of extraction execution",
    )
    extraction_status: ExtractionStatus = Field(..., description="Result status of the extraction attempt")
    segments: List[ExtractedSegment] = Field(
        default_factory=list,
        description="Extracted segments preserving document structural order",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Document-level metadata (e.g. author, title, page_count, encoding)",
    )
    error_message: Optional[str] = Field(
        default=None,
        description="Detailed failure message when status is failed or partial",
    )

    @property
    def text(self) -> str:
        """Concatenated content of all extracted segments."""
        return "\n\n".join(s.content for s in self.segments if s.content)


class ScannedFile(BaseModel):
    """Metadata for a discovered file during folder scanning."""

    path: Path = Field(..., description="Filesystem path of the file")
    filename: str = Field(..., description="Basename of the file")
    extension: str = Field(..., description="Lowercased extension with dot")
    file_size: int = Field(..., description="Size in bytes")
    is_supported: bool = Field(..., description="Whether a registered extractor can process this file")
    detected_type: Optional[str] = Field(default=None, description="Format category if detected")


class ScanReport(BaseModel):
    """Summary report from a directory scan operation."""

    root_path: str = Field(..., description="Root folder scanned")
    total_discovered: int = Field(default=0, description="Total count of files discovered")
    supported_files: List[ScannedFile] = Field(default_factory=list, description="Files eligible for extraction")
    unsupported_files: List[ScannedFile] = Field(default_factory=list, description="Files with unsupported extensions")
    skipped_paths: List[str] = Field(default_factory=list, description="Directories or paths skipped due to rules")
    scan_errors: List[str] = Field(default_factory=list, description="Non-fatal traversal or permission errors")


class ExtractionBatchSummary(BaseModel):
    """Aggregate summary returned after processing a batch of files."""

    total_files: int = Field(default=0, description="Total files attempted")
    successful: int = Field(default=0, description="Count of successfully extracted files")
    partial: int = Field(default=0, description="Count of partially extracted files")
    empty: int = Field(default=0, description="Count of empty files")
    failed: int = Field(default=0, description="Count of failed extraction attempts")
    unsupported: int = Field(default=0, description="Count of unsupported files skipped")
    documents: List[ExtractedDocument] = Field(default_factory=list, description="List of extraction results")
    duration_seconds: float = Field(default=0.0, description="Total execution time in seconds")

