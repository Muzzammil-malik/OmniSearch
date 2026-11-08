"""Extractor and frame sampler for video formats."""

from datetime import datetime, timezone
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from PIL import Image

from app.core.logging import get_logger
from app.ingestion.extractors.base import BaseExtractor
from app.schemas.extraction import ExtractedDocument, ExtractedSegment, ExtractionStatus, SegmentType

logger = get_logger(__name__)

SUPPORTED_VIDEO_EXTENSIONS: Set[str] = {
    ".mp4",
    ".mkv",
    ".webm",
    ".mov",
    ".avi",
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


def sample_video_frames(
    video_path: Path,
    max_frames: int = 16,
    target_fps: float = 1.0,
) -> List[Image.Image]:
    """Sample representative PIL frames from a video file without loading entire stream into RAM.

    Args:
        video_path: Path to the target video file.
        max_frames: Maximum number of frames to return (default 16).
        target_fps: Desired sampling rate in frames per second (default 1 frame/sec).

    Returns:
        List of PIL Image objects sampled across the video timeline.
    """
    frames: List[Image.Image] = []
    path = Path(video_path).resolve()
    if not path.is_file():
        return frames

    try:
        import av

        with av.open(str(path)) as container:
            video_streams = [s for s in container.streams if s.type == "video"]
            if not video_streams:
                return frames

            stream = video_streams[0]
            stream.thread_type = "AUTO"

            # Determine video duration and timestamps
            duration_sec = 0.0
            if stream.duration and stream.time_base:
                duration_sec = float(stream.duration * stream.time_base)
            elif container.duration:
                duration_sec = float(container.duration / av.time.AV_TIME_BASE)

            if duration_sec <= 0:
                # Fallback: grab up to adaptive budget sequentially
                max_budget = min(max_frames, 4)
                for frame in container.decode(stream):
                    pil_img = frame.to_image().convert("RGB")
                    if max(pil_img.size) > 384:
                        pil_img.thumbnail((384, 384), Image.Resampling.BILINEAR)
                    frames.append(pil_img)
                    if len(frames) >= max_budget:
                        break
                return frames

            # Adaptive sampling budget: short clips need fewer frames
            if duration_sec <= 3.0:
                effective_max = min(max_frames, 4)
            elif duration_sec <= 10.0:
                effective_max = min(max_frames, 8)
            else:
                effective_max = min(max_frames, 16)

            # Calculate target sample timestamps in seconds
            total_expected_samples = max(1, min(effective_max, int(math.ceil(duration_sec * target_fps))))
            interval = duration_sec / max(total_expected_samples, 1)
            target_timestamps = [i * interval for i in range(total_expected_samples)]

            current_target_idx = 0
            for frame in container.decode(stream):
                frame_time = float(frame.pts * stream.time_base) if frame.pts is not None and stream.time_base else None
                if frame_time is None:
                    continue

                if current_target_idx < len(target_timestamps):
                    target_time = target_timestamps[current_target_idx]
                    if frame_time >= target_time:
                        pil_img = frame.to_image().convert("RGB")
                        if max(pil_img.size) > 384:
                            pil_img.thumbnail((384, 384), Image.Resampling.BILINEAR)
                        frames.append(pil_img)
                        current_target_idx += 1
                        if len(frames) >= effective_max:
                            break

            # If no frames were collected due to timestamp issues, grab the first available frame
            if not frames:
                container.seek(0)
                for frame in container.decode(stream):
                    pil_img = frame.to_image().convert("RGB")
                    if max(pil_img.size) > 384:
                        pil_img.thumbnail((384, 384), Image.Resampling.BILINEAR)
                    frames.append(pil_img)
                    break

    except Exception as exc:
        logger.warning("Failed sampling frames from video %s: %s", path.name, exc)

    return frames


class VideoExtractor(BaseExtractor):
    """Extracts metadata, codec specifications, and frame summaries from video files."""

    @property
    def supported_extensions(self) -> Set[str]:
        return SUPPORTED_VIDEO_EXTENSIONS

    @property
    def category(self) -> str:
        return "video"

    def extract(self, file_path: Path, sha256: Optional[str] = None) -> ExtractedDocument:
        path = Path(file_path).resolve()
        if not path.is_file():
            return self.create_failed_document(
                file_path=path,
                error_message=f"Video file does not exist: {path}",
                sha256=sha256,
            )

        file_size = path.stat().st_size
        if file_size == 0:
            return self.create_empty_document(file_path=path, sha256=sha256, file_size=0)

        metadata: Dict[str, Any] = {}
        duration_sec = 0.0
        width = 0
        height = 0
        fps = 0.0
        video_codec = ""
        audio_codec = ""

        try:
            import av

            with av.open(str(path)) as container:
                video_streams = [s for s in container.streams if s.type == "video"]
                if not video_streams:
                    return self.create_failed_document(
                        file_path=path,
                        error_message="No video stream detected in container",
                        sha256=sha256,
                        file_size=file_size,
                    )

                v_stream = video_streams[0]
                width = v_stream.width or 0
                height = v_stream.height or 0
                video_codec = v_stream.codec_context.name if v_stream.codec_context else ""

                if v_stream.average_rate:
                    fps = round(float(v_stream.average_rate), 2)
                elif v_stream.base_rate:
                    fps = round(float(v_stream.base_rate), 2)

                audio_streams = [s for s in container.streams if s.type == "audio"]
                if audio_streams and audio_streams[0].codec_context:
                    audio_codec = audio_streams[0].codec_context.name

                if v_stream.duration and v_stream.time_base:
                    duration_sec = float(v_stream.duration * v_stream.time_base)
                elif container.duration:
                    duration_sec = float(container.duration / av.time.AV_TIME_BASE)

                metadata["width"] = width
                metadata["height"] = height
                metadata["aspect_ratio"] = round(width / max(height, 1), 2)
                metadata["fps"] = fps
                metadata["duration_seconds"] = round(duration_sec, 2)
                metadata["duration_formatted"] = _format_duration(duration_sec)
                metadata["video_codec"] = video_codec
                metadata["audio_codec"] = audio_codec
                metadata["format"] = path.suffix.lstrip(".").upper()

            # Build descriptive searchable text content for FTS5 keyword indexing
            desc_parts: List[str] = [
                f"Video file: {path.name}",
                f"Format: {metadata['format']}",
                f"Duration: {metadata['duration_formatted']} ({round(duration_sec, 1)}s)",
                f"Resolution: {width}x{height}",
            ]
            if fps > 0:
                desc_parts.append(f"FPS: {fps}")
            if video_codec:
                desc_parts.append(f"Codec: {video_codec}")
            if audio_codec:
                desc_parts.append(f"Audio Codec: {audio_codec}")

            text_content = " | ".join(desc_parts)

            segment = ExtractedSegment(
                content=text_content,
                segment_index=0,
                segment_type=SegmentType.TEXT_BLOCK,
                metadata={
                    "width": width,
                    "height": height,
                    "aspect_ratio": metadata["aspect_ratio"],
                    "fps": fps,
                    "duration_seconds": metadata["duration_seconds"],
                    "video_codec": video_codec,
                    "audio_codec": audio_codec,
                },
            )

            return ExtractedDocument(
                file_path=str(path),
                filename=path.name,
                extension=path.suffix.lower(),
                file_type="video",
                file_size=file_size,
                sha256=sha256,
                extracted_at=datetime.now(timezone.utc),
                extraction_status=ExtractionStatus.SUCCESS,
                segments=[segment],
                metadata=metadata,
                error_message=None,
            )

        except Exception as exc:
            logger.warning("Failed extracting video %s: %s", path, exc, exc_info=True)
            return self.create_failed_document(
                file_path=path,
                error_message=f"Failed to decode video: {exc}",
                sha256=sha256,
                file_size=file_size,
            )

