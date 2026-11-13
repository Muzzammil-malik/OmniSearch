"""Path filtering and validation rules for filesystem watcher."""

from pathlib import Path
from typing import Optional, Set, Union
from app.ingestion.registry import ExtractorRegistry, default_registry
from app.ingestion.scanner import DEFAULT_EXCLUDED_DIRECTORIES

IGNORED_FILE_PREFIXES = ("~", ".~", "tmp", ".tmp")
IGNORED_FILE_EXTENSIONS: Set[str] = {
    ".tmp",
    ".crdownload",
    ".part",
    ".swp",
    ".swo",
    ".lock",
    ".bak",
}


def should_ignore_path(path: Union[str, Path], is_directory: bool = False) -> bool:
    """Determine whether a filesystem path should be completely ignored by the watcher.

    Args:
        path: Target filesystem path.
        is_directory: True if the event refers to a directory rather than a file.

    Returns:
        True if the path should be skipped, False otherwise.
    """
    if is_directory:
        return True

    p = Path(path)
    name = p.name.lower()
    suffix = p.suffix.lower()

    # Ignore transient / temporary files or hidden files
    if name.startswith("."):
        return True

    for prefix in IGNORED_FILE_PREFIXES:
        if name.startswith(prefix):
            return True

    if suffix in IGNORED_FILE_EXTENSIONS:
        return True

    # Check each directory component against standard excluded folders or hidden directories
    for part in p.parts[:-1]:
        if part.startswith(".") or part.lower() in {d.lower() for d in DEFAULT_EXCLUDED_DIRECTORIES}:
            return True

    return False


def is_supported_file(
    path: Union[str, Path],
    registry: Optional[ExtractorRegistry] = None,
) -> bool:
    """Check if the given file has an extension supported by OmniSearch extractors."""
    reg = registry or default_registry
    ext = Path(path).suffix.lower()
    return ext in reg.get_all_supported_extensions()

