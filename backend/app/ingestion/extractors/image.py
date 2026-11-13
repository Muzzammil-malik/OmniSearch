"""Extractor for raster and photograph image formats."""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from PIL import Image, ExifTags

from app.core.logging import get_logger
from app.ingestion.extractors.base import BaseExtractor
from app.schemas.extraction import ExtractedDocument, ExtractedSegment, ExtractionStatus, SegmentType

logger = get_logger(__name__)

SUPPORTED_IMAGE_EXTENSIONS: Set[str] = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".bmp",
    ".gif",
    ".tiff",
    ".tif",
}


class ImageExtractor(BaseExtractor):
    """Extracts metadata and visual representation summaries from image files."""

    @property
    def supported_extensions(self) -> Set[str]:
        return SUPPORTED_IMAGE_EXTENSIONS

    @property
    def category(self) -> str:
        return "image"

    def extract(self, file_path: Path, sha256: Optional[str] = None) -> ExtractedDocument:
        path = Path(file_path).resolve()
        if not path.is_file():
            return self.create_failed_document(
                file_path=path,
                error_message=f"Image file does not exist: {path}",
                sha256=sha256,
            )

        file_size = path.stat().st_size
        if file_size == 0:
            return self.create_empty_document(file_path=path, sha256=sha256, file_size=0)

        metadata: Dict[str, Any] = {}
        try:
            with Image.open(path) as img:
                width, height = img.size
                image_format = (img.format or path.suffix.lstrip(".").upper()).upper()
                mode = img.mode

                metadata["width"] = width
                metadata["height"] = height
                metadata["format"] = image_format
                metadata["mode"] = mode
                metadata["aspect_ratio"] = round(width / max(height, 1), 2)

                # Parse EXIF tags if present
                exif_data: Dict[str, str] = {}
                try:
                    raw_exif = img.getexif()
                    if raw_exif:
                        for tag_id, value in raw_exif.items():
                            tag_name = ExifTags.TAGS.get(tag_id, str(tag_id))
                            # Keep readable string-convertible metadata
                            if isinstance(value, (str, int, float)):
                                exif_data[tag_name] = str(value)
                except Exception as exif_err:
                    logger.debug("Failed extracting EXIF data from %s: %s", path.name, exif_err)

                if exif_data:
                    metadata["exif"] = exif_data
                    if "Make" in exif_data or "Model" in exif_data:
                        camera = f"{exif_data.get('Make', '')} {exif_data.get('Model', '')}".strip()
                        metadata["camera"] = camera
                    if "DateTime" in exif_data:
                        metadata["date_taken"] = exif_data["DateTime"]

                # Generate a concise searchable description for FTS5 keyword indexing
                desc_parts: List[str] = [
                    f"Image file: {path.name}",
                    f"Dimensions: {width}x{height}",
                    f"Format: {image_format}",
                    f"Mode: {mode}",
                ]
                if "camera" in metadata:
                    desc_parts.append(f"Camera: {metadata['camera']}")
                if "date_taken" in metadata:
                    desc_parts.append(f"Date: {metadata['date_taken']}")

                text_content = " | ".join(desc_parts)

                segment = ExtractedSegment(
                    content=text_content,
                    segment_index=0,
                    segment_type=SegmentType.TEXT_BLOCK,
                    metadata={
                        "width": width,
                        "height": height,
                        "format": image_format,
                        "aspect_ratio": metadata["aspect_ratio"],
                    },
                )

                return ExtractedDocument(
                    file_path=str(path),
                    filename=path.name,
                    extension=path.suffix.lower(),
                    file_type="image",
                    file_size=file_size,
                    sha256=sha256,
                    extracted_at=datetime.now(timezone.utc),
                    extraction_status=ExtractionStatus.SUCCESS,
                    segments=[segment],
                    metadata=metadata,
                    error_message=None,
                )

        except Exception as exc:
            logger.warning("Failed extracting image %s: %s", path, exc, exc_info=True)
            return self.create_failed_document(
                file_path=path,
                error_message=f"Failed to decode image: {exc}",
                sha256=sha256,
                file_size=file_size,
            )

