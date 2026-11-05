"""Domain and application exceptions for OmniSearch."""

from typing import Any, Dict, Optional


class OmniSearchException(Exception):
    """Base exception for all domain and application errors in OmniSearch."""

    def __init__(
        self,
        message: str,
        code: str = "INTERNAL_ERROR",
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}


class NotFoundError(OmniSearchException):
    """Raised when a requested resource is not found."""

    def __init__(
        self,
        message: str,
        code: str = "NOT_FOUND",
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message=message, code=code, status_code=404, details=details)


class FolderNotFoundError(NotFoundError):
    """Raised when a specified folder ID or path is not found in database."""

    def __init__(self, folder_id_or_path: Any) -> None:
        super().__init__(
            message=f"Folder not found: {folder_id_or_path}",
            code="FOLDER_NOT_FOUND",
            details={"identifier": str(folder_id_or_path)},
        )


class JobNotFoundError(NotFoundError):
    """Raised when a specified indexing job ID is not found."""

    def __init__(self, job_id: int) -> None:
        super().__init__(
            message=f"Indexing job #{job_id} not found",
            code="JOB_NOT_FOUND",
            details={"job_id": job_id},
        )


class ValidationError(OmniSearchException):
    """Raised when client input fails business validation."""

    def __init__(
        self,
        message: str,
        code: str = "VALIDATION_ERROR",
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message=message, code=code, status_code=400, details=details)


class InvalidFolderPathError(ValidationError):
    """Raised when a path string does not exist on disk or is not a directory."""

    def __init__(self, path: str, reason: str = "Path does not exist or is not a directory") -> None:
        super().__init__(
            message=f"Invalid folder path '{path}': {reason}",
            code="INVALID_FOLDER_PATH",
            details={"path": path, "reason": reason},
        )


class ConflictError(OmniSearchException):
    """Raised when an operation conflicts with the current application state."""

    def __init__(
        self,
        message: str,
        code: str = "CONFLICT",
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message=message, code=code, status_code=409, details=details)


class DuplicateFolderError(ConflictError):
    """Raised when attempting to register a folder path that is already registered."""

    def __init__(self, path: str) -> None:
        super().__init__(
            message=f"Folder path '{path}' is already registered",
            code="DUPLICATE_FOLDER",
            details={"path": path},
        )


class IndexingInProgressError(ConflictError):
    """Raised when an indexing job is triggered while another is already running."""

    def __init__(self, active_job_id: Optional[int] = None) -> None:
        super().__init__(
            message="An indexing job is already currently running. Please wait for it to complete.",
            code="INDEXING_IN_PROGRESS",
            details={"active_job_id": active_job_id},
        )


class SearchExecutionError(OmniSearchException):
    """Raised when search execution encounters an unrecoverable engine failure."""

    def __init__(self, query: str, reason: str) -> None:
        super().__init__(
            message=f"Search failed for query '{query}': {reason}",
            code="SEARCH_EXECUTION_ERROR",
            status_code=500,
            details={"query": query, "reason": reason},
        )


class ServiceUnavailableError(OmniSearchException):
    """Raised when an optional or degraded subsystem is unavailable."""

    def __init__(self, service_name: str, reason: str) -> None:
        super().__init__(
            message=f"Service '{service_name}' is currently unavailable: {reason}",
            code="SERVICE_UNAVAILABLE",
            status_code=503,
            details={"service": service_name, "reason": reason},
        )

