"""Standardized API error response schemas."""

from datetime import datetime, timezone
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """Consistent error payload returned across all API endpoints."""

    error: str = Field(..., description="High-level error classification")
    detail: str = Field(..., description="Human-readable error description")
    code: str = Field(default="INTERNAL_ERROR", description="Machine-readable error code")
    status_code: int = Field(default=500, description="HTTP status code")
    details: Optional[Dict[str, Any]] = Field(default=None, description="Optional diagnostic attributes")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of the error response",
    )

