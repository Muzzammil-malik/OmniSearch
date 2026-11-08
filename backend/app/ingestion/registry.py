"""Centralized registry for file format extractors."""

from pathlib import Path
from typing import Dict, List, Optional, Set
from app.core.logging import get_logger
from app.ingestion.extractors.base import BaseExtractor
from app.ingestion.extractors.csv import CsvExtractor
from app.ingestion.extractors.docx import DocxExtractor
from app.ingestion.extractors.html import HtmlExtractor
from app.ingestion.extractors.image import ImageExtractor
from app.ingestion.extractors.audio import AudioExtractor
from app.ingestion.extractors.video import VideoExtractor
from app.ingestion.extractors.pdf import PdfExtractor
from app.ingestion.extractors.pptx import PptxExtractor
from app.ingestion.extractors.text import TextExtractor
from app.ingestion.extractors.xlsx import XlsxExtractor

logger = get_logger(__name__)


class ExtractorRegistry:
    """Manages available format extractors and maps extensions to their respective handlers."""

    def __init__(self) -> None:
        self._extractors: List[BaseExtractor] = []
        self._extension_map: Dict[str, BaseExtractor] = {}

    def register(self, extractor: BaseExtractor) -> None:
        """Register an extractor instance and map its supported extensions."""
        self._extractors.append(extractor)
        for ext in extractor.supported_extensions:
            normalized_ext = ext.lower()
            if normalized_ext in self._extension_map:
                logger.debug("Overriding extractor for extension '%s'", normalized_ext)
            self._extension_map[normalized_ext] = extractor

    def get_extractor_for_extension(self, extension: str) -> Optional[BaseExtractor]:
        """Look up the appropriate extractor by lowercased extension."""
        return self._extension_map.get(extension.lower())

    def get_extractor_for_file(self, file_path: Path) -> Optional[BaseExtractor]:
        """Look up the appropriate extractor for a target file path."""
        ext = Path(file_path).suffix.lower()
        return self.get_extractor_for_extension(ext)

    def is_supported(self, file_path: Path) -> bool:
        """Check if an extractor is available for the given file."""
        return self.get_extractor_for_file(file_path) is not None

    def get_all_supported_extensions(self) -> Set[str]:
        """Return the set of all registered file extensions."""
        return set(self._extension_map.keys())


def create_default_registry() -> ExtractorRegistry:
    """Build and return an ExtractorRegistry pre-populated with standard extractors."""
    registry = ExtractorRegistry()
    registry.register(PdfExtractor())
    registry.register(DocxExtractor())
    registry.register(PptxExtractor())
    registry.register(XlsxExtractor())
    registry.register(TextExtractor())
    registry.register(CsvExtractor())
    registry.register(HtmlExtractor())
    registry.register(ImageExtractor())
    registry.register(AudioExtractor())
    registry.register(VideoExtractor())
    return registry


# Global default instance
default_registry = create_default_registry()

