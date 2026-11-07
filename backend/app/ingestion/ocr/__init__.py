"""OCR fallback subsystem for image-based documents."""

from app.ingestion.ocr.service import BaseOcrProvider, OcrService, PyMuPdfOcrProvider

__all__ = ["BaseOcrProvider", "OcrService", "PyMuPdfOcrProvider"]

