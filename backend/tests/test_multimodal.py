"""Automated unit and integration tests for Multimodal Search (Images, Audio, Video)."""

import io
import math
from pathlib import Path
import struct
import wave
import pytest
from PIL import Image

from app.database.connection import DatabaseConnectionManager
from app.database.initialization import init_db
from app.database.repositories.files import FileRepository
from app.database.repositories.folders import FolderRepository
from app.embeddings.test_embedder import DeterministicTestEmbedder
from app.ingestion.extractors.audio import AudioExtractor
from app.ingestion.extractors.image import ImageExtractor
from app.ingestion.extractors.video import VideoExtractor, sample_video_frames
from app.ingestion.file_detector import FileTypeDetector
from app.schemas.extraction import ExtractionStatus
from app.schemas.search import SearchFilter
from app.search.hybrid_search import HybridSearchEngine
from app.search.keyword_search import KeywordSearchEngine
from app.search.semantic_search import SemanticSearchEngine
from app.services.indexer import IndexingService
from app.services.semantic_pipeline import SemanticPipeline
from app.vector_store.chroma import ChromaVectorStore


def create_test_image(path: Path, width: int = 200, height: int = 150, color=(255, 120, 0)) -> Path:
    """Helper to generate a valid test image file."""
    img = Image.new("RGB", (width, height), color=color)
    img.save(path)
    return path


def create_test_wav(path: Path, duration_sec: float = 1.0, sample_rate: int = 16000) -> Path:
    """Helper to generate a valid synthetic WAV audio file."""
    num_samples = int(duration_sec * sample_rate)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)  # Mono
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sample_rate)
        # 440Hz sine wave tone
        frames = bytearray()
        for i in range(num_samples):
            val = int(32767.0 * 0.5 * math.sin(2.0 * math.pi * 440.0 * i / sample_rate))
            frames.extend(struct.pack("<h", val))
        wf.writeframes(frames)
    return path


# ---------------------------------------------------------------------------
# 1. File Type Detection & Signature Tests
# ---------------------------------------------------------------------------

def test_multimodal_file_detector_extensions():
    """Verify image, audio, and video extensions are recognized."""
    detector = FileTypeDetector()
    for ext in [".jpg", ".png", ".webp", ".mp3", ".wav", ".flac", ".mp4", ".mkv"]:
        assert detector.is_supported_extension(ext) is True

    assert detector.get_format_category(".jpg") == "image"
    assert detector.get_format_category(".png") == "image"
    assert detector.get_format_category(".mp3") == "audio"
    assert detector.get_format_category(".wav") == "audio"
    assert detector.get_format_category(".mp4") == "video"
    assert detector.get_format_category(".mkv") == "video"


def test_multimodal_file_detector_image_signature(tmp_path: Path):
    """Verify image file header signature validation."""
    valid_png = tmp_path / "photo.png"
    create_test_image(valid_png)
    is_valid, cat, err = FileTypeDetector.validate_file(valid_png)
    assert is_valid is True
    assert cat == "image"
    assert err is None

    fake_png = tmp_path / "fake.png"
    fake_png.write_bytes(b"This is not a png at all")
    is_valid, cat, err = FileTypeDetector.validate_file(fake_png)
    assert is_valid is False
    assert cat == "invalid_image"


def test_multimodal_file_detector_rejects_disguised_executable(tmp_path: Path):
    """Verify executable binary disguised with media extension is rejected."""
    bad_mp4 = tmp_path / "video.mp4"
    bad_mp4.write_bytes(b"MZ\x90\x00\x03\x00FakePEHeaderInVideo")
    is_valid, cat, err = FileTypeDetector.validate_file(bad_mp4)
    assert is_valid is False
    assert cat == "rejected_executable"


# ---------------------------------------------------------------------------
# 2. Extractors Tests
# ---------------------------------------------------------------------------

def test_image_extractor(tmp_path: Path):
    """Verify ImageExtractor extracts dimensions, format, and description."""
    img_path = tmp_path / "sunset.jpg"
    create_test_image(img_path, width=640, height=480)

    extractor = ImageExtractor()
    assert extractor.can_extract(img_path) is True
    doc = extractor.extract(img_path)

    assert doc.extraction_status == ExtractionStatus.SUCCESS
    assert doc.file_type == "image"
    assert doc.metadata["width"] == 640
    assert doc.metadata["height"] == 480
    assert len(doc.segments) == 1
    assert "sunset.jpg" in doc.segments[0].content
    assert "640x480" in doc.segments[0].content


def test_image_extractor_corrupt(tmp_path: Path):
    """Verify ImageExtractor handles corrupted image gracefully."""
    corrupt = tmp_path / "broken.jpg"
    corrupt.write_bytes(b"\xff\xd8\xffcorruptedtruncatedbytes")
    extractor = ImageExtractor()
    doc = extractor.extract(corrupt)
    assert doc.extraction_status == ExtractionStatus.FAILED
    assert "Failed to decode" in doc.error_message


def test_audio_extractor(tmp_path: Path):
    """Verify AudioExtractor extracts duration, channels, sample rate."""
    wav_path = tmp_path / "podcast.wav"
    create_test_wav(wav_path, duration_sec=1.5, sample_rate=16000)

    extractor = AudioExtractor()
    assert extractor.can_extract(wav_path) is True
    doc = extractor.extract(wav_path)

    assert doc.extraction_status == ExtractionStatus.SUCCESS
    assert doc.file_type == "audio"
    assert doc.metadata["channels"] == 1
    assert doc.metadata["sample_rate"] == 16000
    assert doc.metadata["duration_seconds"] >= 1.4
    assert len(doc.segments) == 1
    assert "podcast.wav" in doc.segments[0].content


def test_video_extractor_missing_file():
    """Verify VideoExtractor handles missing file gracefully."""
    extractor = VideoExtractor()
    doc = extractor.extract(Path("nonexistent_video_file.mp4"))
    assert doc.extraction_status == ExtractionStatus.FAILED


# ---------------------------------------------------------------------------
# 3. Deterministic Embedder Multimodal Vectors
# ---------------------------------------------------------------------------

def test_deterministic_embedder_multimodal_methods(tmp_path: Path):
    """Verify DeterministicTestEmbedder implements unit-length multimodal vectors."""
    embedder = DeterministicTestEmbedder(dimension=768)

    img_path = tmp_path / "nature.jpg"
    audio_path = tmp_path / "ambient.wav"
    vid_path = tmp_path / "clip.mp4"

    vec_img = embedder.embed_image(str(img_path))
    vec_audio = embedder.embed_audio(str(audio_path))
    vec_vid = embedder.embed_video(str(vid_path))

    for vec in [vec_img, vec_audio, vec_vid]:
        assert len(vec) == 768
        norm = math.sqrt(sum(x * x for x in vec))
        assert pytest.approx(norm, abs=1e-4) == 1.0

    # Same input produces deterministic vector
    assert embedder.embed_image(str(img_path)) == vec_img


# ---------------------------------------------------------------------------
# 4. End-to-End Multimodal Ingestion & Search Integration
# ---------------------------------------------------------------------------

@pytest.fixture
def multimodal_env(tmp_path: Path):
    """Set up isolated database, vector store, and services with multimodal files."""
    db_file = tmp_path / "multimodal.db"
    vectors_dir = tmp_path / "vectors"
    library_dir = tmp_path / "library"
    library_dir.mkdir()

    # 1. Create media files
    img1 = library_dir / "ocean_sunset.jpg"
    create_test_image(img1, width=800, height=600, color=(255, 90, 0))

    audio1 = library_dir / "guitar_solo.wav"
    create_test_wav(audio1, duration_sec=2.0)

    txt1 = library_dir / "sunset_notes.txt"
    txt1.write_text("Notes about watching the sunset at the beach.", encoding="utf-8")

    # 2. Init DB and components
    db = init_db(db_file)
    vector_store = ChromaVectorStore(persist_dir=vectors_dir)
    embedder = DeterministicTestEmbedder(dimension=768)
    pipeline = SemanticPipeline(db=db, embedder=embedder, vector_store=vector_store)
    indexer = IndexingService(db=db, semantic_pipeline=pipeline)

    return db, vector_store, embedder, pipeline, indexer, library_dir


def test_multimodal_indexing_and_vector_persistence(multimodal_env):
    """Verify indexing folder with text, image, and audio files populates SQLite and ChromaDB."""
    db, vector_store, embedder, pipeline, indexer, library_dir = multimodal_env

    # Register folder
    with db.connection() as conn:
        f_record = FolderRepository.get_or_create(conn, str(library_dir))
        f_id = f_record.id

    job = indexer.index_folder(library_dir, generate_embeddings=True)
    assert job.status == "completed"
    assert job.successful_files == 3

    # Check files in SQLite
    with db.connection() as conn:
        files = FileRepository.list_by_folder(conn, f_id)
        assert len(files) == 3
        types = {f.file_type for f in files}
        assert "image" in types
        assert "audio" in types
        assert "text" in types

    # Check ChromaDB vectors
    assert vector_store.count() == 3
    chunk_ids = vector_store.get_all_chunk_ids()
    assert len(chunk_ids) == 3


def test_multimodal_semantic_search_retrieval(multimodal_env):
    """Verify semantic search retrieves media items with content_type and metadata."""
    db, vector_store, embedder, pipeline, indexer, library_dir = multimodal_env

    with db.connection() as conn:
        FolderRepository.get_or_create(conn, str(library_dir))
    indexer.index_folder(library_dir, generate_embeddings=True)

    semantic_engine = SemanticSearchEngine(db=db, vector_store=vector_store, embedder=embedder)
    res = semantic_engine.search("sunset")

    assert res.total_results >= 1
    # Check that image result contains content_type
    image_results = [r for r in res.results if r.file_type == "image"]
    assert len(image_results) == 1
    item = image_results[0]
    assert item.content_type == "image"
    assert item.filename == "ocean_sunset.jpg"
    assert item.media_metadata is not None
    assert item.media_metadata.get("width") == 800


def test_multimodal_hybrid_search_fusion(multimodal_env):
    """Verify hybrid search returns fused ranking including image and audio results."""
    db, vector_store, embedder, pipeline, indexer, library_dir = multimodal_env

    with db.connection() as conn:
        FolderRepository.get_or_create(conn, str(library_dir))
    indexer.index_folder(library_dir, generate_embeddings=True)

    keyword_engine = KeywordSearchEngine(db=db)
    semantic_engine = SemanticSearchEngine(db=db, vector_store=vector_store, embedder=embedder)
    hybrid_engine = HybridSearchEngine(db=db, keyword_engine=keyword_engine, semantic_engine=semantic_engine)

    res = hybrid_engine.search("guitar solo")
    assert res.total_results >= 1
    # Audio result found
    audio_results = [r for r in res.results if r.file_type == "audio"]
    assert len(audio_results) == 1
    assert audio_results[0].content_type == "audio"
    assert audio_results[0].media_metadata.get("channels") == 1


def test_multimodal_file_type_filtering(multimodal_env):
    """Verify search filtering by specific multimodal file_types."""
    db, vector_store, embedder, pipeline, indexer, library_dir = multimodal_env

    with db.connection() as conn:
        FolderRepository.get_or_create(conn, str(library_dir))
    indexer.index_folder(library_dir, generate_embeddings=True)

    semantic_engine = SemanticSearchEngine(db=db, vector_store=vector_store, embedder=embedder)

    # Filter to only images
    filter_img = SearchFilter(file_types=["image"])
    res_img = semantic_engine.search("sunset", filters=filter_img)
    for r in res_img.results:
        assert r.file_type == "image"
        assert r.content_type == "image"


def test_multimodal_deletion_cleans_vectors(multimodal_env):
    """Verify deleting a media file removes it from SQLite and vector store."""
    db, vector_store, embedder, pipeline, indexer, library_dir = multimodal_env

    with db.connection() as conn:
        FolderRepository.get_or_create(conn, str(library_dir))
    indexer.index_folder(library_dir, generate_embeddings=True)
    assert vector_store.count() == 3

    # Delete ocean_sunset.jpg
    img_path = library_dir / "ocean_sunset.jpg"
    deleted = indexer.delete_single_file(img_path)
    assert deleted is True

    # Check vector count decreased
    assert vector_store.count() == 2
    with db.connection() as conn:
        files = FileRepository.list_by_folder(conn, 1)
        assert len(files) == 2
        assert all(f.filename != "ocean_sunset.jpg" for f in files)
