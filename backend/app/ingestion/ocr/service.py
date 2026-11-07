"""Local OCR fallback service using PyMuPDF embedded Tesseract engine."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional
import pymupdf

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class BaseOcrProvider(ABC):
    """Abstract interface for local OCR engines."""

    @abstractmethod
    def is_available(self) -> bool:
        """Check if OCR provider and required language data are available."""
        pass

    @abstractmethod
    def extract_text_from_page(self, page: pymupdf.Page, dpi: int = 150) -> str:
        """Extract text from a document page using OCR."""
        pass


class PyMuPdfOcrProvider(BaseOcrProvider):
    """Local-first in-process OCR using PyMuPDF's built-in Tesseract C-API."""

    def __init__(
        self,
        tessdata_dir: Optional[Path] = None,
        language: str = "eng",
    ) -> None:
        self.language = language
        if tessdata_dir is not None:
            self.tessdata_dir = Path(tessdata_dir)
        else:
            settings = get_settings()
            self.tessdata_dir = settings.resolved_ocr_tessdata_dir

    def is_available(self) -> bool:
        """Verify presence of language traineddata file."""
        if not self.tessdata_dir.exists():
            return False
        lang_file = self.tessdata_dir / f"{self.language}.traineddata"
        return lang_file.is_file() and lang_file.stat().st_size > 0

    def extract_text_from_page(self, page: pymupdf.Page, dpi: int = 150) -> str:
        """Perform OCR on a single PyMuPDF page.

        Returns extracted text, or an empty string on error or blank page.
        """
        if not self.is_available():
            logger.debug("OCR requested but tessdata for '%s' not found at %s", self.language, self.tessdata_dir)
            return ""

        try:
            # Handle rotation, page rect validity
            if page.rect.is_empty or page.rect.is_infinite:
                return ""

            textpage = page.get_textpage_ocr(
                tessdata=str(self.tessdata_dir),
                language=self.language,
                dpi=dpi,
                full=True,
            )
            return textpage.extractText().strip()
        except Exception as exc:
            logger.warning("OCR failed for page %d: %s", page.number + 1, exc)
            return ""


class OcrService:
    """High-level service coordinating OCR text extraction for document ingestors."""

    def __init__(self, provider: Optional[BaseOcrProvider] = None) -> None:
        self.provider = provider or PyMuPdfOcrProvider()

    @property
    def is_available(self) -> bool:
        return self.provider.is_available()

    def ocr_page(self, page: pymupdf.Page, dpi: int = 150) -> str:
        """Extract text from page with OCR fallback."""
        return self.provider.extract_text_from_page(page, dpi=dpi)

