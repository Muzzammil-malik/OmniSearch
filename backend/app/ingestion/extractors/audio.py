"""Extractor for audio formats."""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from app.core.logging import get_logger
from app.ingestion.extractors.base import BaseExtractor
from app.schemas.extraction import ExtractedDocument, ExtractedSegment, ExtractionStatus, SegmentType

logger = get_logger(__name__)

SUPPORTED_AUDIO_EXTENSIONS: Set[str] = {
    ".mp3",
    ".wav",
    ".flac",
    ".m4a",
    ".aac",
    ".ogg",
    ".oga",
    ".opus",
    ".wma",
}


def _format_duration(seconds: float) -> str:
    """Format duration in seconds as MM:SS or HH:MM:SS string."""
    total_sec = int(round(seconds))
    hrs = total_sec // 3600
    mins = (total_sec % 3600) // 60
    secs = total_sec % 60
    if hrs > 0:
        return f"{hrs:02d}:{mins:02d}:{secs:02d}"
    return f"{mins:02d}:{secs:02d}"


class AudioExtractor(BaseExtractor):
    """Extracts metadata, audio properties, and ID3 tags from audio files."""

    @property
    def supported_extensions(self) -> Set[str]:
        return SUPPORTED_AUDIO_EXTENSIONS

    @property
    def category(self) -> str:
        return "audio"

    def extract(self, file_path: Path, sha256: Optional[str] = None) -> ExtractedDocument:
        path = Path(file_path).resolve()
        if not path.is_file():
            return self.create_failed_document(
                file_path=path,
                error_message=f"Audio file does not exist: {path}",
                sha256=sha256,
            )

        file_size = path.stat().st_size
        if file_size == 0:
            return self.create_empty_document(file_path=path, sha256=sha256, file_size=0)

        metadata: Dict[str, Any] = {}
        duration_sec = 0.0
        sample_rate = 0
        channels = 0
        codec_name = ""

        try:
            # 1. Inspect using PyAV for metadata tags and audio stream properties
            import av

            with av.open(str(path)) as container:
                # Container tags (ID3, Vorbis, etc.)
                tags: Dict[str, str] = {}
                for k, v in container.metadata.items():
                    if isinstance(v, (str, int, float)):
                        tags[k.lower()] = str(v)

                audio_streams = [s for s in container.streams if s.type == "audio"]
                if not audio_streams:
                    return self.create_failed_document(
                        file_path=path,
                        error_message="No audio stream detected in container",
                        sha256=sha256,
                        file_size=file_size,
                    )

                audio_stream = audio_streams[0]
                sample_rate = audio_stream.rate or 0
                channels = audio_stream.channels or 0
                codec_name = audio_stream.codec_context.name if audio_stream.codec_context else ""

                # Compute duration
                if audio_stream.duration and audio_stream.time_base:
                    duration_sec = float(audio_stream.duration * audio_stream.time_base)
                elif container.duration:
                    duration_sec = float(container.duration / av.time.AV_TIME_BASE)

                metadata["duration_seconds"] = round(duration_sec, 2)
                metadata["duration_formatted"] = _format_duration(duration_sec)
                metadata["sample_rate"] = sample_rate
                metadata["channels"] = channels
                metadata["codec"] = codec_name
                metadata["format"] = path.suffix.lstrip(".").upper()

                # Extract common audio metadata tags
                for key in ["title", "artist", "album", "genre", "date"]:
                    val = tags.get(key)
                    if val:
                        metadata[key] = val

            # Generate descriptive searchable text content for FTS5 keyword indexing
            desc_parts: List[str] = [
                f"Audio file: {path.name}",
                f"Format: {metadata['format']}",
                f"Duration: {metadata['duration_formatted']} ({round(duration_sec, 1)}s)",
            ]
            if metadata.get("artist"):
                desc_parts.append(f"Artist: {metadata['artist']}")
            if metadata.get("title"):
                desc_parts.append(f"Title: {metadata['title']}")
            if metadata.get("album"):
                desc_parts.append(f"Album: {metadata['album']}")
            if metadata.get("genre"):
                desc_parts.append(f"Genre: {metadata['genre']}")
            if channels > 0:
                ch_desc = "Mono" if channels == 1 else "Stereo" if channels == 2 else f"{channels} channels"
                desc_parts.append(f"Audio: {ch_desc} ({sample_rate}Hz, {codec_name})")

            text_content = " | ".join(desc_parts)

            segment = ExtractedSegment(
                content=text_content,
                segment_index=0,
                segment_type=SegmentType.TEXT_BLOCK,
                metadata={
                    "duration_seconds": metadata["duration_seconds"],
                    "sample_rate": sample_rate,
                    "channels": channels,
                    "codec": codec_name,
                },
            )

            return ExtractedDocument(
                file_path=str(path),
                filename=path.name,
                extension=path.suffix.lower(),
                file_type="audio",
                file_size=file_size,
                sha256=sha256,
                extracted_at=datetime.now(timezone.utc),
                extraction_status=ExtractionStatus.SUCCESS,
                segments=[segment],
                metadata=metadata,
                error_message=None,
            )

        except Exception as exc:
            logger.warning("Failed extracting audio %s: %s", path, exc, exc_info=True)
            return self.create_failed_document(
                file_path=path,
                error_message=f"Failed to decode audio: {exc}",
                sha256=sha256,
                file_size=file_size,
            )

