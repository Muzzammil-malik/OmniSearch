"""Persistent indexing service coordinating scanning, extraction, processing, and SQLite persistence."""

from datetime import datetime, timezone
import json
from pathlib import Path
from threading import Thread
from typing import Any, List, Optional, Set, Union
from app.core.exceptions import (
    FolderNotFoundError,
    IndexingInProgressError,
    InvalidFolderPathError,
    JobNotFoundError,
)
from app.core.logging import get_logger
from app.database.connection import DatabaseConnectionManager
from app.database.repositories.chunks import ChunkRepository
from app.database.repositories.embeddings import ChunkEmbeddingRepository
from app.database.repositories.files import FileRepository
from app.database.repositories.folders import FolderRepository
from app.database.repositories.jobs import JobRepository
from app.ingestion.coordinator import IngestionCoordinator
from app.ingestion.hashing import try_calculate_sha256
from app.ingestion.scanner import FolderScanner
from app.processing.pipeline import ContentProcessingPipeline
from app.schemas.extraction import ExtractionStatus, ScannedFile
from app.schemas.indexing import (
    IndexJobResponse,
    IndexingStatsResponse,
    IndexingStatusResponse,
)
from app.schemas.processing import FileRecord, IndexJobRecord, IndexJobStatus

logger = get_logger(__name__)


class IndexingService:
    """Manages the full indexing lifecycle with duplicate prevention, chunk replacement, and fault isolation."""

    def __init__(
        self,
        db: DatabaseConnectionManager,
        scanner: Optional[FolderScanner] = None,
        coordinator: Optional[IngestionCoordinator] = None,
        pipeline: Optional[ContentProcessingPipeline] = None,
        semantic_pipeline: Optional[Any] = None,
    ) -> None:
        self.db = db
        self.scanner = scanner or FolderScanner()
        self.coordinator = coordinator or IngestionCoordinator()
        self.pipeline = pipeline or ContentProcessingPipeline()
        self.semantic_pipeline = semantic_pipeline

    def index_folder(
        self,
        folder_path: Union[str, Path],
        reconcile_deleted: bool = True,
        force_reindex: bool = False,
        generate_embeddings: bool = False,
    ) -> IndexJobRecord:
        """Scan, process, and persist all supported files within a folder.

        Args:
            folder_path: Target directory path on local disk.
            reconcile_deleted: Whether to remove database records for files deleted from disk.
            force_reindex: If True, reprocesses files even if size, mtime, and hash match.

        Returns:
            Final IndexJobRecord reflecting processing metrics and job outcome.
        """
        resolved_folder = Path(folder_path).resolve()
        if not resolved_folder.exists() or not resolved_folder.is_dir():
            raise ValueError(f"Folder path does not exist or is not a directory: {resolved_folder}")

        logger.info("Initiating persistent index for folder: %s", resolved_folder)

        # 1. Discover files via recursive folder scanner
        scan_report = self.scanner.scan(resolved_folder)
        supported_files = scan_report.supported_files

        # 2. Register or fetch folder record and create index job in DB
        with self.db.transaction() as conn:
            folder_record = FolderRepository.get_or_create(conn, str(resolved_folder))
            folder_id = folder_record.id
            assert folder_id is not None
            job_id = JobRepository.create(conn, total_files=len(supported_files))

        processed_count = 0
        successful_count = 0
        failed_count = 0
        skipped_count = 0

        # 3. Process each discovered file with individual fault isolation
        for scanned_file in supported_files:
            file_path = scanned_file.path
            processed_count += 1

            try:
                # Check modification stats
                stat_res = file_path.stat()
                mtime_iso = datetime.fromtimestamp(stat_res.st_mtime, tz=timezone.utc).isoformat()
                file_size = stat_res.st_size

                # Check if file already exists in database
                with self.db.connection() as conn:
                    existing_file = FileRepository.get_by_path(conn, str(file_path))

                # Calculate SHA-256 once per file to avoid redundant re-hashing
                current_sha256 = try_calculate_sha256(file_path)

                # Reliable unchanged-file detection:
                # Do not rely solely on size/mtime; verify SHA-256 before skipping
                if (
                    not force_reindex
                    and existing_file
                    and existing_file.status == ExtractionStatus.SUCCESS.value
                    and existing_file.sha256 is not None
                    and current_sha256 is not None
                    and current_sha256 == existing_file.sha256
                ):
                    # Content is verified identical via SHA-256 hash.
                    # Update modification metadata in DB if mtime changed on disk (e.g. touch/copy)
                    if existing_file.modified_at != mtime_iso or existing_file.size_bytes != file_size:
                        with self.db.transaction() as conn:
                            updated_rec = existing_file.model_copy(
                                update={"modified_at": mtime_iso, "size_bytes": file_size}
                            )
                            FileRepository.upsert(conn, updated_rec)

                    logger.debug("File content unchanged (verified via SHA-256), skipping: %s", file_path.name)
                    skipped_count += 1
                    with self.db.transaction() as conn:
                        JobRepository.update_progress(
                            conn, job_id, processed_count, successful_count, failed_count, skipped_count
                        )
                    continue

                # File is new or modified: perform Phase 2 extraction using precomputed hash
                extracted_doc = self.coordinator.extract_document(
                    scanned_file,
                    compute_hash=False,
                    precomputed_sha256=current_sha256,
                )

                if extracted_doc.extraction_status in (ExtractionStatus.FAILED, ExtractionStatus.UNSUPPORTED):
                    logger.warning("Indexing failed for file '%s': %s", file_path.name, extracted_doc.error_message)
                    failed_count += 1

                    failed_record = FileRecord(
                        folder_id=folder_id,
                        path=str(file_path),
                        filename=file_path.name,
                        extension=file_path.suffix.lower(),
                        file_type=extracted_doc.file_type,
                        sha256=extracted_doc.sha256,
                        size_bytes=file_size,
                        modified_at=mtime_iso,
                        status=extracted_doc.extraction_status.value,
                        error_message=extracted_doc.error_message,
                        metadata_json=json.dumps(extracted_doc.metadata),
                    )

                    with self.db.transaction() as conn:
                        saved_file_id = FileRepository.upsert(conn, failed_record)
                        # Safe failed re-indexing:
                        # If this file was previously successfully indexed, PRESERVE its existing chunks!
                        # Only delete chunks if this file was never successfully indexed before.
                        if not existing_file or existing_file.status != ExtractionStatus.SUCCESS.value:
                            ChunkRepository.delete_by_file_id(conn, saved_file_id)
                        else:
                            logger.info(
                                "Preserved previously committed chunks for file '%s' following failed re-indexing",
                                file_path.name,
                            )

                        JobRepository.update_progress(
                            conn, job_id, processed_count, successful_count, failed_count, skipped_count
                        )
                    continue

                # Extraction succeeded (or empty document): run Phase 3 processing pipeline
                norm_doc, chunks = self.pipeline.process_document(extracted_doc)

                file_record = FileRecord(
                    folder_id=folder_id,
                    path=str(file_path),
                    filename=file_path.name,
                    extension=file_path.suffix.lower(),
                    file_type=extracted_doc.file_type,
                    sha256=extracted_doc.sha256,
                    size_bytes=file_size,
                    modified_at=mtime_iso,
                    status=extracted_doc.extraction_status.value,
                    error_message=extracted_doc.error_message,
                    metadata_json=json.dumps(norm_doc.metadata),
                )

                # Persist file and chunks atomically in a single transaction
                with self.db.transaction() as conn:
                    saved_file_id = FileRepository.upsert(conn, file_record)
                    # Replace old chunks atomically
                    ChunkRepository.delete_by_file_id(conn, saved_file_id)
                    if chunks:
                        ChunkRepository.insert_chunks(conn, saved_file_id, chunks)

                    successful_count += 1
                    JobRepository.update_progress(
                        conn, job_id, processed_count, successful_count, failed_count, skipped_count
                    )

            except Exception as exc:
                logger.error("Unhandled error processing file '%s': %s", file_path.name, exc, exc_info=True)
                failed_count += 1
                with self.db.transaction() as conn:
                    if existing_file:
                        err_record = existing_file.model_copy(
                            update={
                                "status": ExtractionStatus.FAILED.value,
                                "error_message": f"Processing error: {exc}",
                            }
                        )
                        FileRepository.upsert(conn, err_record)
                    JobRepository.update_progress(
                        conn, job_id, processed_count, successful_count, failed_count, skipped_count
                    )

        # 4. Deleted file reconciliation (remove database records for files deleted from disk)
        if reconcile_deleted:
            present_paths = {str(f.path) for f in supported_files}
            with self.db.transaction() as conn:
                deleted_paths = FileRepository.delete_missing_in_folder(conn, folder_id, present_paths)
                if deleted_paths:
                    logger.info("Reconciliation removed %d deleted file records from database", len(deleted_paths))
            if self.semantic_pipeline:
                try:
                    self.semantic_pipeline.reconcile_vector_store()
                except Exception as exc:
                    logger.warning("Vector store reconciliation warning: %s", exc)

        # 4b. Optional semantic embedding generation
        if generate_embeddings and self.semantic_pipeline:
            try:
                embedded_count = self.semantic_pipeline.sync_embeddings()
                logger.info("Generated semantic embeddings for %d chunks", embedded_count)
            except Exception as exc:
                logger.error("Error generating semantic embeddings during indexing: %s", exc, exc_info=True)

        # 5. Finalize job status
        final_status = (
            IndexJobStatus.COMPLETED if failed_count == 0
            else IndexJobStatus.COMPLETED_WITH_ERRORS
        )
        with self.db.transaction() as conn:
            JobRepository.finish(conn, job_id, final_status)
            final_job = JobRepository.get_by_id(conn, job_id)

        assert final_job is not None
        logger.info(
            "Indexing job #%d finished with status '%s' (Total: %d, Success: %d, Skipped: %d, Failed: %d)",
            job_id,
            final_status.value,
            final_job.total_files,
            final_job.successful_files,
            final_job.skipped_files,
            final_job.failed_files,
        )
        return final_job

    def trigger_indexing(
        self,
        folder_id: Optional[int] = None,
        folder_path: Optional[str] = None,
        force_reindex: bool = False,
        reconcile_deleted: bool = True,
        generate_embeddings: bool = True,
        background: bool = False,
    ) -> IndexJobRecord:
        """Trigger an indexing operation with validation, concurrency checks, and optional background execution."""
        # 1. Concurrency check: reject if another job is already actively running
        with self.db.connection() as conn:
            running_job = JobRepository.get_running_job(conn)
            if running_job is not None:
                raise IndexingInProgressError(active_job_id=running_job.id)

        # 2. Resolve target directories
        target_paths: List[Path] = []
        if folder_id is not None:
            with self.db.connection() as conn:
                folder_rec = FolderRepository.get_by_id(conn, folder_id)
            if not folder_rec:
                raise FolderNotFoundError(folder_id)
            target_paths.append(Path(folder_rec.path))
        elif folder_path is not None:
            p = Path(folder_path).resolve()
            if not p.exists() or not p.is_dir():
                raise InvalidFolderPathError(str(p))
            target_paths.append(p)
        else:
            with self.db.connection() as conn:
                registered = FolderRepository.list_all(conn)
            enabled_folders = [f for f in registered if f.enabled]
            if not enabled_folders:
                raise InvalidFolderPathError(
                    "", reason="No active folders registered. Register a folder first."
                )
            target_paths.extend([Path(f.path) for f in enabled_folders])

        def run_work() -> IndexJobRecord:
            last_job: Optional[IndexJobRecord] = None
            for tp in target_paths:
                last_job = self.index_folder(
                    folder_path=tp,
                    reconcile_deleted=reconcile_deleted,
                    force_reindex=force_reindex,
                    generate_embeddings=generate_embeddings,
                )
            assert last_job is not None
            return last_job

        if background:
            thread = Thread(target=run_work, daemon=True)
            thread.start()
            import time
            time.sleep(0.05)
            with self.db.connection() as conn:
                job = JobRepository.get_running_job(conn) or JobRepository.get_latest(conn)
            if job:
                return job

        return run_work()

    def get_job(self, job_id: int) -> Optional[IndexJobRecord]:
        """Fetch indexing job by ID."""
        with self.db.connection() as conn:
            return JobRepository.get_by_id(conn, job_id)

    def get_latest_job(self) -> Optional[IndexJobRecord]:
        """Fetch the most recent indexing job."""
        with self.db.connection() as conn:
            return JobRepository.get_latest(conn)

    def list_recent_jobs(self, limit: int = 20) -> List[IndexJobRecord]:
        """List recent indexing jobs."""
        with self.db.connection() as conn:
            return JobRepository.list_recent(conn, limit=limit)

    def get_indexing_status(self) -> IndexingStatusResponse:
        """Inspect current indexing engine status and recent jobs."""
        with self.db.connection() as conn:
            running = JobRepository.get_running_job(conn)
            recent = JobRepository.list_recent(conn, limit=10)

        current_job_resp = (
            IndexJobResponse(
                id=running.id,
                status=running.status,
                total_files=running.total_files,
                processed_files=running.processed_files,
                successful_files=running.successful_files,
                failed_files=running.failed_files,
                skipped_files=running.skipped_files,
                started_at=running.started_at,
                finished_at=running.finished_at,
                error_message=running.error_message,
            )
            if running and running.id is not None
            else None
        )

        recent_resps = [
            IndexJobResponse(
                id=j.id,
                status=j.status,
                total_files=j.total_files,
                processed_files=j.processed_files,
                successful_files=j.successful_files,
                failed_files=j.failed_files,
                skipped_files=j.skipped_files,
                started_at=j.started_at,
                finished_at=j.finished_at,
                error_message=j.error_message,
            )
            for j in recent
            if j.id is not None
        ]

        return IndexingStatusResponse(
            is_indexing=running is not None,
            current_job=current_job_resp,
            recent_jobs=recent_resps,
        )

    def get_indexing_stats(self) -> IndexingStatsResponse:
        """Calculate global aggregated indexing metrics."""
        with self.db.connection() as conn:
            folders = FolderRepository.list_all(conn)
            total_files = FileRepository.count_total(conn)
            status_counts = FileRepository.count_by_status(conn)
            total_chunks = ChunkRepository.count_total(conn)
            embedded_chunks = ChunkEmbeddingRepository.count_embedded(conn)
            unembedded_chunks = ChunkEmbeddingRepository.count_unembedded(conn)
            total_size = FileRepository.get_total_size_bytes(conn)

        return IndexingStatsResponse(
            total_folders=len(folders),
            total_files=total_files,
            successful_files=status_counts.get("success", 0),
            failed_files=status_counts.get("failed", 0) + status_counts.get("unsupported", 0),
            total_chunks=total_chunks,
            embedded_chunks=embedded_chunks,
            unembedded_chunks=unembedded_chunks,
            total_size_bytes=total_size,
        )

