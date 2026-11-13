"""Index jobs repository for tracking batch indexing execution and progress."""

from datetime import datetime, timezone
import sqlite3
from typing import List, Optional
from app.schemas.processing import IndexJobRecord, IndexJobStatus


class JobRepository:
    """Data access repository for index_jobs table."""

    @staticmethod
    def create(conn: sqlite3.Connection, total_files: int = 0) -> int:
        """Create a new pending/running indexing job."""
        now_iso = datetime.now(timezone.utc).isoformat()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO index_jobs (
                status, total_files, processed_files, successful_files,
                failed_files, skipped_files, started_at
            ) VALUES (?, ?, 0, 0, 0, 0, ?);
            """,
            (IndexJobStatus.RUNNING.value, total_files, now_iso),
        )
        job_id = cursor.lastrowid
        cursor.close()
        return job_id

    @staticmethod
    def update_progress(
        conn: sqlite3.Connection,
        job_id: int,
        processed_files: int,
        successful_files: int,
        failed_files: int,
        skipped_files: int,
    ) -> None:
        """Update job file processing counters."""
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE index_jobs
            SET processed_files = ?,
                successful_files = ?,
                failed_files = ?,
                skipped_files = ?
            WHERE id = ?;
            """,
            (processed_files, successful_files, failed_files, skipped_files, job_id),
        )
        cursor.close()

    @staticmethod
    def finish(
        conn: sqlite3.Connection,
        job_id: int,
        status: IndexJobStatus,
        error_message: Optional[str] = None,
    ) -> None:
        """Finalize job lifecycle with final status and finished timestamp."""
        now_iso = datetime.now(timezone.utc).isoformat()
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE index_jobs
            SET status = ?,
                finished_at = ?,
                error_message = ?
            WHERE id = ?;
            """,
            (status.value, now_iso, error_message, job_id),
        )
        cursor.close()

    @classmethod
    def get_by_id(cls, conn: sqlite3.Connection, job_id: int) -> Optional[IndexJobRecord]:
        """Fetch job record by primary key."""
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM index_jobs WHERE id = ?;", (job_id,))
        row = cursor.fetchone()
        cursor.close()
        return cls._row_to_record(row) if row else None

    @classmethod
    def list_recent(cls, conn: sqlite3.Connection, limit: int = 20) -> List[IndexJobRecord]:
        """Fetch recent jobs ordered by started_at descending."""
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM index_jobs ORDER BY id DESC LIMIT ?;", (limit,))
        rows = cursor.fetchall()
        cursor.close()
        return [cls._row_to_record(r) for r in rows]

    @classmethod
    def get_running_job(cls, conn: sqlite3.Connection) -> Optional[IndexJobRecord]:
        """Fetch the currently running job if one exists."""
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM index_jobs WHERE status = ? ORDER BY id DESC LIMIT 1;",
            (IndexJobStatus.RUNNING.value,),
        )
        row = cursor.fetchone()
        cursor.close()
        return cls._row_to_record(row) if row else None

    @classmethod
    def get_latest(cls, conn: sqlite3.Connection) -> Optional[IndexJobRecord]:
        """Fetch the single most recent job record."""
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM index_jobs ORDER BY id DESC LIMIT 1;")
        row = cursor.fetchone()
        cursor.close()
        return cls._row_to_record(row) if row else None

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> IndexJobRecord:
        return IndexJobRecord(
            id=row["id"],
            status=IndexJobStatus(row["status"]),
            total_files=row["total_files"],
            processed_files=row["processed_files"],
            successful_files=row["successful_files"],
            failed_files=row["failed_files"],
            skipped_files=row["skipped_files"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
            error_message=row["error_message"],
        )

