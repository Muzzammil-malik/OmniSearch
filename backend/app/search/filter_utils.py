"""Search filter normalization utilities for format categories and extensions."""

from typing import List, Optional
from app.ingestion.file_detector import FileTypeDetector

# Canonical mapping from user/UI filter aliases to underlying database file_type categories
_CATEGORY_ALIAS_MAP = {
    "image": ["image"],
    "images": ["image"],
    "audio": ["audio"],
    "audios": ["audio"],
    "video": ["video"],
    "videos": ["video"],
    "pdf": ["pdf"],
    "docx": ["docx"],
    "doc": ["docx"],
    "pptx": ["pptx"],
    "ppt": ["pptx"],
    "xlsx": ["xlsx", "csv"],
    "sheets": ["xlsx", "csv"],
    "spreadsheet": ["xlsx", "csv"],
    "spreadsheets": ["xlsx", "csv"],
    "csv": ["csv"],
    "code": ["code"],
    "markdown": ["markdown"],
    "md": ["markdown"],
    "text": ["text"],
    "txt": ["text"],
    "html": ["html"],
    "htm": ["html"],
}


def normalize_file_type_filters(file_types: Optional[List[str]]) -> Optional[List[str]]:
    """Normalize input file_types filter criteria to canonical database category identifiers.

    Handles category names (e.g. 'image', 'images', 'sheets', 'md'), specific extensions
    (e.g. '.png', 'mp4', 'py'), and ensures consistent filtering across KeywordSearchEngine,
    SemanticSearchEngine, and HybridSearchEngine.

    Returns:
        Deduplicated list of canonical category strings, or None if input is empty/None.
    """
    if not file_types:
        return None

    normalized: List[str] = []
    for item in file_types:
        if not item:
            continue
        raw = item.strip().lower().lstrip(".")
        if not raw:
            continue

        if raw in _CATEGORY_ALIAS_MAP:
            normalized.extend(_CATEGORY_ALIAS_MAP[raw])
        else:
            # Check if this raw string is a recognized file extension (e.g. 'png' -> '.png')
            cat = FileTypeDetector.get_format_category("." + raw)
            if cat != "unsupported":
                normalized.append(cat)
            else:
                normalized.append(raw)

    if not normalized:
        return None

    # Deduplicate while preserving order
    return list(dict.fromkeys(normalized))

