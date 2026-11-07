"""Comprehensive integration tests for Phase 9: File watching, debouncing, incremental indexing,

reconciliation, modified-file safety, and local OCR.
"""

from datetime import datetime, timezone
import io
from pathlib import Path
import time
from unittest.mock import MagicMock, patch

import fitz
from PIL import Image, ImageDraw, ImageFont
import pytest

from app.core.config import Settings, get_settings
from app.database.connection import DatabaseConnectionManager
from app.database.migrations import apply_migrations
from app.database.repositories.chunks import ChunkRepository
from app.database.repositories.files import FileRepository
from app.database.repositories.folders import FolderRepository
from app.ingestion.extractors.pdf import PdfExtractor
from app.ingestion.ocr.service import PyMuPdfOcrProvider
from app.schemas.extraction import ExtractionStatus, ScannedFile
from app.schemas.processing import DocumentChunk, FileRecord
from app.services.change_coordinator import ChangeCoordinator
from app.services.indexer import IndexingService
from app.watcher.debouncer import ChangeDebouncer
from app.watcher.events import FileChangeEvent, FileChangeType
from app.watcher.filters import is_supported_file, should_ignore_path
from app.watcher.reconciler import StartupReconciler
from app.watcher.service import FileSystemWatcher


@pytest.fixture
def test_env(tmp_path: Path):
    """Create isolated database and environment for incremental indexing testing."""
    db_file = tmp_path / "omnisearch_watcher_test.db"
    db = DatabaseConnectionManager(db_path=db_file)
    with db.connection() as conn:
        apply_migrations(conn)

    watch_dir = tmp_path / "watched_folder"
    watch_dir.mkdir(parents=True, exist_ok=True)

    with db.transaction() as conn:
        folder_rec = FolderRepository.get_or_create(conn, str(watch_dir))

    mock_semantic_pipeline = MagicMock()
    mock_semantic_pipeline.vector_store = MagicMock()
    mock_semantic_pipeline.sync_embeddings.return_value = 0

    indexing_service = IndexingService(
        db=db,
        semantic_pipeline=mock_semantic_pipeline,
    )

    return db, watch_dir, folder_rec.id, indexing_service, mock_semantic_pipeline


# -------------------------------------------------------------------------
# 1. Filters & Path Rules
# -------------------------------------------------------------------------

def test_filters_ignore_and_supported():
    """Verify system ignore rules and file extension support."""
    assert should_ignore_path(".git/objects/abc", False) is True
    assert should_ignore_path(".omnisearch/db.sqlite", False) is True
    assert should_ignore_path("node_modules/package/index.js", False) is True
    assert should_ignore_path("temp/~$report.docx", False) is True
    assert should_ignore_path("documents/.DS_Store", False) is True

    assert is_supported_file("document.pdf") is True
    assert is_supported_file("notes.md") is True
    assert is_supported_file("code.py") is True
    assert is_supported_file("table.csv") is True
    assert is_supported_file("unknown.xyz123") is False


# -------------------------------------------------------------------------
# 2. Event Debouncer Coalescing
# -------------------------------------------------------------------------

def test_debouncer_coalesces_rapid_events():
    """Verify rapid events on the same file are coalesced into a single action."""
    dispatched = []

    def on_event(ev: FileChangeEvent):
        dispatched.append(ev)

    debouncer = ChangeDebouncer(on_event=on_event, debounce_ms=100)
    try:
        fpath = Path("test_file.txt").resolve()

        # Emit burst of MODIFIED events
        for _ in range(5):
            debouncer.record_event(FileChangeType.MODIFIED, fpath)
            time.sleep(0.01)

        # Wait for debounce settlement
        time.sleep(0.25)
        assert len(dispatched) == 1
        assert dispatched[0].change_type == FileChangeType.MODIFIED
        assert dispatched[0].path == fpath

    finally:
        debouncer.stop()


def test_debouncer_drops_transient_create_delete():
    """Verify a file created and deleted within the debounce window is dropped completely."""
    dispatched = []

    def on_event(ev: FileChangeEvent):
        dispatched.append(ev)

    debouncer = ChangeDebouncer(on_event=on_event, debounce_ms=150)
    try:
        fpath = Path("temp_scratch.tmp.txt").resolve()

        debouncer.record_event(FileChangeType.CREATED, fpath)
        time.sleep(0.02)
        debouncer.record_event(FileChangeType.DELETED, fpath)

        time.sleep(0.3)
        assert len(dispatched) == 0

    finally:
        debouncer.stop()


def test_debouncer_coalesces_create_and_move():
    """Verify a file created then moved settles as a CREATED event on destination."""
    dispatched = []

    def on_event(ev: FileChangeEvent):
        dispatched.append(ev)

    debouncer = ChangeDebouncer(on_event=on_event, debounce_ms=100)
    try:
        src_path = Path("temp_orig.txt").resolve()
        dest_path = Path("final_name.txt").resolve()

        debouncer.record_event(FileChangeType.CREATED, src_path)
        time.sleep(0.02)
        debouncer.record_event(FileChangeType.MOVED, src_path, dest_path=dest_path)

        time.sleep(0.25)
        assert len(dispatched) == 1
        assert dispatched[0].change_type == FileChangeType.CREATED
        assert dispatched[0].path == dest_path

    finally:
        debouncer.stop()


# -------------------------------------------------------------------------
# 3. Single-File Operations in IndexingService
# -------------------------------------------------------------------------

def test_index_single_file_lifecycle(test_env):
    """Test full cycle: index new file, verify chunks, modify file, delete file."""
    db, watch_dir, folder_id, indexing_service, mock_semantic = test_env

    target_file = watch_dir / "quickstart.md"
    target_file.write_text("# Quickstart Guide\n\nWelcome to OmniSearch local-first search system.", encoding="utf-8")

    # 1. Index single file
    rec = indexing_service.index_single_file(target_file, folder_id=folder_id)
    assert rec is not None
    assert rec.status == ExtractionStatus.SUCCESS.value

    with db.connection() as conn:
        db_file = FileRepository.get_by_path(conn, str(target_file.resolve()))
        assert db_file is not None
        assert db_file.id is not None
        chunks = ChunkRepository.get_by_file_id(conn, db_file.id)
        assert len(chunks) > 0
        original_chunk_id = chunks[0].id

    # 2. Re-indexing without changes should skip re-extraction
    rec2 = indexing_service.index_single_file(target_file, folder_id=folder_id)
    assert rec2 is not None
    assert rec2.sha256 == rec.sha256

    # 3. Modify content
    target_file.write_text("# Quickstart Guide Updated\n\nNew section on neural vector search.", encoding="utf-8")
    rec3 = indexing_service.index_single_file(target_file, folder_id=folder_id)
    assert rec3 is not None
    assert rec3.sha256 != rec.sha256

    with db.connection() as conn:
        updated_chunks = ChunkRepository.get_by_file_id(conn, db_file.id)
        assert len(updated_chunks) > 0
        assert updated_chunks[0].id != original_chunk_id
        # Vector cleanup should have been invoked for old chunk
        mock_semantic.vector_store.delete.assert_called()

    # 4. Delete single file
    deleted = indexing_service.delete_single_file(target_file)
    assert deleted is True

    with db.connection() as conn:
        db_file_after = FileRepository.get_by_path(conn, str(target_file.resolve()))
        assert db_file_after is None
        chunks_after = ChunkRepository.get_by_file_id(conn, db_file.id)
        assert len(chunks_after) == 0


def test_modified_file_safety_preserves_valid_content(test_env):
    """Requirement 2: If re-extraction fails on a modified file, previous valid searchable content is preserved."""
    db, watch_dir, folder_id, indexing_service, _ = test_env

    test_file = watch_dir / "critical_data.txt"
    test_file.write_text("Valid initial text content for critical data analysis.", encoding="utf-8")

    # Index initially
    rec = indexing_service.index_single_file(test_file, folder_id=folder_id)
    assert rec is not None
    assert rec.status == ExtractionStatus.SUCCESS.value

    with db.connection() as conn:
        db_file = FileRepository.get_by_path(conn, str(test_file.resolve()))
        assert db_file is not None
        initial_chunks = ChunkRepository.get_by_file_id(conn, db_file.id)
        assert len(initial_chunks) > 0
        initial_chunk_ids = [c.id for c in initial_chunks]

    # Modify file and mock extractor to simulate extraction failure
    test_file.write_text("Corrupt binary payload that causes parser failure.", encoding="utf-8")

    with patch.object(
        indexing_service.coordinator,
        "extract_document",
        return_value=MagicMock(
            extraction_status=ExtractionStatus.FAILED,
            error_message="Corrupted file stream header",
            file_type="txt",
            sha256="deadbeef1234",
            metadata={},
        ),
    ):
        failed_rec = indexing_service.index_single_file(test_file, folder_id=folder_id)
        assert failed_rec is not None
        assert failed_rec.status == ExtractionStatus.FAILED.value
        assert "Corrupted file stream header" in failed_rec.error_message

    # Verify modified-file safety: Previous valid chunks still exist in SQLite!
    with db.connection() as conn:
        current_chunks = ChunkRepository.get_by_file_id(conn, db_file.id)
        assert len(current_chunks) == len(initial_chunks)
        assert [c.id for c in current_chunks] == initial_chunk_ids


# -------------------------------------------------------------------------
# 4. Startup Reconciliation Diff Logic
# -------------------------------------------------------------------------

def test_startup_reconciler_fast_path(test_env):
    """Requirement 4: Untouched files are verified via size/mtime without re-hashing."""
    db, watch_dir, folder_id, indexing_service, _ = test_env

    # Create two files
    file_a = watch_dir / "file_a.txt"
    file_b = watch_dir / "file_b.txt"
    file_a.write_text("Hello file A", encoding="utf-8")
    file_b.write_text("Hello file B", encoding="utf-8")

    indexing_service.index_single_file(file_a, folder_id=folder_id)
    indexing_service.index_single_file(file_b, folder_id=folder_id)

    # Initialize reconciler
    reconciler = StartupReconciler(db=db, indexing_service=indexing_service)

    # Reconcile when nothing changed on disk
    with patch("app.watcher.reconciler.try_calculate_sha256") as mock_hash:
        summary = reconciler.reconcile_folder(folder_id, watch_dir)
        # Fast-path check: untouched files match size & mtime, so try_calculate_sha256 should NOT be called!
        assert summary.checked_files == 2
        assert summary.unmodified_files == 2
        assert summary.created_files == 0
        assert summary.modified_files == 0
        assert summary.deleted_files == 0
        mock_hash.assert_not_called()


def test_startup_reconciler_detects_offline_changes(test_env):
    """Test reconciler detects files created, modified, or deleted while application was offline."""
    db, watch_dir, folder_id, indexing_service, _ = test_env

    file_1 = watch_dir / "persist.txt"
    file_to_delete = watch_dir / "remove_me.txt"
    file_1.write_text("Original content", encoding="utf-8")
    file_to_delete.write_text("Will be deleted offline", encoding="utf-8")

    indexing_service.index_single_file(file_1, folder_id=folder_id)
    indexing_service.index_single_file(file_to_delete, folder_id=folder_id)

    # Simulate offline actions:
    # 1. Modify file_1
    time.sleep(0.05)
    file_1.write_text("Updated offline content with new words", encoding="utf-8")
    # 2. Delete file_to_delete
    file_to_delete.unlink()
    # 3. Create new offline file
    new_file = watch_dir / "offline_new.txt"
    new_file.write_text("Created while offline", encoding="utf-8")

    reconciler = StartupReconciler(db=db, indexing_service=indexing_service)
    summary = reconciler.reconcile_folder(folder_id, watch_dir)

    assert summary.created_files == 1
    assert summary.modified_files == 1
    assert summary.deleted_files == 1

    with db.connection() as conn:
        assert FileRepository.get_by_path(conn, str(file_to_delete.resolve())) is None
        assert FileRepository.get_by_path(conn, str(new_file.resolve())) is not None


# -------------------------------------------------------------------------
# 5. Change Coordinator Routing
# -------------------------------------------------------------------------

def test_change_coordinator_worker_routing(test_env):
    """Test that ChangeCoordinator worker thread processes events asynchronously."""
    _, watch_dir, folder_id, indexing_service, _ = test_env

    coordinator = ChangeCoordinator(indexing_service=indexing_service, max_queue_size=50)
    coordinator.start()

    try:
        assert coordinator.is_running is True

        sample_file = watch_dir / "coordinator_test.txt"
        sample_file.write_text("Coordinator worker verification content", encoding="utf-8")

        enqueued = coordinator.enqueue(
            FileChangeEvent(
                change_type=FileChangeType.CREATED,
                path=sample_file.resolve(),
            )
        )
        assert enqueued is True

        # Wait for worker thread to process
        deadline = time.time() + 3.0
        while time.time() < deadline and coordinator.processed_count < 1:
            time.sleep(0.05)

        assert coordinator.processed_count == 1
        assert coordinator.error_count == 0

    finally:
        coordinator.stop()


# -------------------------------------------------------------------------
# 6. Local In-Process OCR Verification
# -------------------------------------------------------------------------

def test_local_ocr_on_image_only_pdf(tmp_path: Path):
    """Requirement 8 & Verification: PyMuPDF in-process OCR extracts text from an image-only PDF page."""
    settings = get_settings()
    if not settings.ocr_enabled:
        pytest.skip("OCR is disabled in settings")

    tessdata_dir = settings.resolved_ocr_tessdata_dir
    eng_file = tessdata_dir / "eng.traineddata"
    if not eng_file.exists():
        pytest.skip(f"Tessdata file not present at {eng_file}")

    ocr_provider = PyMuPdfOcrProvider(tessdata_dir=tessdata_dir, language="eng")
    assert ocr_provider.is_available() is True

    # 1. Generate an image-only PDF page using Pillow and PyMuPDF
    img = Image.new("RGB", (600, 200), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    # Draw clear text
    draw.text((30, 80), "Phase 9 OCR Local Test", fill=(0, 0, 0))

    img_bytes = io.BytesIO()
    img.save(img_bytes, format="PNG")
    img_bytes.seek(0)

    doc = fitz.open()
    page = doc.new_page(width=600, height=200)
    page.insert_image(page.rect, stream=img_bytes.getvalue())

    pdf_path = tmp_path / "scanned_invoice.pdf"
    doc.save(str(pdf_path))
    doc.close()

    # 2. Extract using PdfExtractor with OCR fallback enabled
    pdf_extractor = PdfExtractor(ocr_enabled=True)
    result = pdf_extractor.extract(pdf_path)

    assert result.extraction_status == ExtractionStatus.SUCCESS
    assert "Phase" in result.text
    assert "OCR" in result.text
    assert result.metadata.get("ocr_applied") is True


def test_standard_text_pdf_does_not_trigger_ocr(tmp_path: Path):
    """Requirement 8: Standard text PDFs must NOT have OCR applied."""
    doc = fitz.open()
    page = doc.new_page(width=500, height=200)
    page.insert_text((50, 50), "This is native digital selectable text in PDF.", fontsize=14)
    pdf_path = tmp_path / "native_text.pdf"
    doc.save(str(pdf_path))
    doc.close()

    pdf_extractor = PdfExtractor(ocr_enabled=True)
    result = pdf_extractor.extract(pdf_path)

    assert result.extraction_status == ExtractionStatus.SUCCESS
    assert "native digital selectable text" in result.text
    # Metadata should NOT have ocr_applied
    assert result.metadata.get("ocr_applied", False) is False
