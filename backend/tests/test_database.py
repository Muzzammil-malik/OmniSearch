"""Tests for SQLite database architecture, foreign-key cascades, transactions, and recovery."""

from pathlib import Path
import pytest
from app.database.connection import DatabaseConnectionManager
from app.database.initialization import init_db, recover_interrupted_jobs
from app.database.migrations import apply_migrations
from app.database.repositories.chunks import ChunkRepository
from app.database.repositories.files import FileRepository
from app.database.repositories.folders import FolderRepository
from app.database.repositories.jobs import JobRepository
from app.database.repositories.settings import SettingRepository
from app.schemas.processing import DocumentChunk, FileRecord, IndexJobStatus


def test_init_db_creates_tables_and_indexes(tmp_path: Path) -> None:
    db_file = tmp_path / "test.db"
    db = init_db(db_path=db_file)

    with db.connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = {row[0] for row in cursor.fetchall()}
        cursor.close()

    assert "folders" in tables
    assert "files" in tables
    assert "chunks" in tables
    assert "index_jobs" in tables
    assert "settings" in tables
    assert "schema_migrations" in tables


def test_foreign_key_cascade_deletion(tmp_path: Path) -> None:
    db = init_db(db_path=tmp_path / "cascade.db")

    with db.transaction() as conn:
        folder = FolderRepository.get_or_create(conn, "/user/documents")
        file_rec = FileRecord(
            folder_id=folder.id,
            path="/user/documents/doc.txt",
            filename="doc.txt",
            extension=".txt",
            file_type="text",
            modified_at="2026-11-03T00:00:00Z",
            status="success",
        )
        file_id = FileRepository.upsert(conn, file_rec)

        chunk = DocumentChunk(
            chunk_index=0,
            content="Sample chunk content",
            token_count=10,
            source_segment_index=0,
        )
        ChunkRepository.insert_chunks(conn, file_id, [chunk])

    # Verify records exist
    with db.connection() as conn:
        assert FileRepository.get_by_id(conn, file_id) is not None
        assert len(ChunkRepository.get_by_file_id(conn, file_id)) == 1

    # Delete folder -> should CASCADE delete file and chunks
    with db.transaction() as conn:
        assert folder.id is not None
        deleted = FolderRepository.delete(conn, folder.id)
        assert deleted

    with db.connection() as conn:
        assert FileRepository.get_by_id(conn, file_id) is None
        assert len(ChunkRepository.get_by_file_id(conn, file_id)) == 0


def test_transaction_rollback_on_exception(tmp_path: Path) -> None:
    db = init_db(db_path=tmp_path / "rollback.db")

    with pytest.raises(RuntimeError):
        with db.transaction() as conn:
            FolderRepository.get_or_create(conn, "/user/test_rollback")
            raise RuntimeError("Forced simulation error")

    # Verify that the folder was NOT persisted due to rollback
    with db.connection() as conn:
        folders = FolderRepository.list_all(conn)
        assert len(folders) == 0


def test_persistence_across_connection_reopen(tmp_path: Path) -> None:
    db_file = tmp_path / "persistent.db"

    # Session 1: Create and write
    db1 = init_db(db_path=db_file)
    with db1.transaction() as conn:
        SettingRepository.set(conn, "app_mode", "desktop_local")
        FolderRepository.get_or_create(conn, "/data/folder1")

    # Session 2: Reopen from same file
    db2 = DatabaseConnectionManager(db_path=db_file)
    with db2.connection() as conn:
        val = SettingRepository.get(conn, "app_mode")
        assert val == "desktop_local"

        folders = FolderRepository.list_all(conn)
        assert len(folders) == 1
        assert folders[0].path.endswith("folder1")


def test_interrupted_jobs_recovery_policy(tmp_path: Path) -> None:
    db = init_db(db_path=tmp_path / "recovery.db", recover_jobs=False)

    with db.transaction() as conn:
        job_id = JobRepository.create(conn, total_files=10)
        # Job starts in 'running' status

    # Simulate process restart by calling recover_interrupted_jobs
    recovered_count = recover_interrupted_jobs(db)
    assert recovered_count == 1

    with db.connection() as conn:
        job = JobRepository.get_by_id(conn, job_id)
        assert job is not None
        assert job.status == IndexJobStatus.INTERRUPTED
        assert job.finished_at is not None
        assert "interrupted" in (job.error_message or "").lower()


def test_phase3_migration_startup_regression(tmp_path: Path) -> None:
    """Regression test reproducing startup with an existing Phase 3 database containing 'name' NOT NULL."""
    import sqlite3
    from app.database.migrations import migration_v1

    db_file = tmp_path / "phase3_existing.db"
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()

    # 1. Establish exact Phase 3 schema_migrations table with name NOT NULL
    cursor.execute("""
    CREATE TABLE schema_migrations (
        version INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        applied_at TEXT NOT NULL
    );
    """)
    cursor.execute(
        "INSERT INTO schema_migrations (version, name, applied_at) VALUES (?, ?, ?);",
        (1, "001_initial_schema", "2026-11-03T16:22:47.927258+00:00"),
    )

    # 2. Apply migration_v1 tables and seed pre-existing Phase 3 data
    migration_v1(conn)
    cursor.execute("""
    INSERT INTO files (id, path, filename, extension, file_type, modified_at, indexed_at, status, metadata_json)
    VALUES (1, 'C:/docs/contract.pdf', 'contract.pdf', '.pdf', 'pdf', '2026-11-03T00:00:00Z', '2026-11-03T00:00:00Z', 'success', '{}');
    """)
    cursor.execute("""
    INSERT INTO chunks (id, file_id, chunk_index, content, token_count)
    VALUES (1, 1, 0, 'Confidential non-disclosure agreement clauses', 10);
    """)
    conn.commit()
    conn.close()

    # 3. Trigger startup init_db on the existing Phase 3 database (must not fail with IntegrityError)
    db = init_db(db_path=db_file)

    # 4. Verify migrations are recorded properly with non-null names
    with db.connection() as verify_conn:
        cur = verify_conn.cursor()
        cur.execute("SELECT version, name, applied_at FROM schema_migrations ORDER BY version ASC;")
        rows = cur.fetchall()
        assert len(rows) == 3
        assert rows[0][0] == 1
        assert rows[0][1] == "001_initial_schema"
        assert rows[1][0] == 2
        assert rows[1][1] == "002_fts5_search"
        assert rows[2][0] == 3
        assert rows[2][1] == "003_semantic_embeddings"

        # 5. Verify pre-existing data was preserved and backfilled into chunks_fts
        cur.execute("SELECT chunk_id, file_id, filename, content FROM chunks_fts WHERE chunks_fts MATCH 'confidential';")
        match = cur.fetchone()
        assert match is not None
        assert match[0] == 1
        assert match[2] == "contract.pdf"
        cur.close()


def test_schema_migrations_missing_name_retroactively_added(tmp_path: Path) -> None:
    """Verify that an interim database lacking 'name' column is safely upgraded."""
    import sqlite3

    db_file = tmp_path / "interim_schema.db"
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE schema_migrations (
        version INTEGER PRIMARY KEY,
        applied_at TEXT NOT NULL
    );
    """)
    conn.commit()
    conn.close()

    db = init_db(db_path=db_file)
    with db.connection() as verify_conn:
        cur = verify_conn.cursor()
        cur.execute("PRAGMA table_info(schema_migrations);")
        cols = {row[1] for row in cur.fetchall()}
        assert "name" in cols
        cur.close()


def test_folder_repository_list_active(tmp_path: Path) -> None:
    """Verify FolderRepository.list_active returns only enabled folders."""
    db = init_db(db_path=tmp_path / "folders.db")

    with db.transaction() as conn:
        f1 = FolderRepository.get_or_create(conn, "/docs/active1")
        f2 = FolderRepository.get_or_create(conn, "/docs/disabled")
        f3 = FolderRepository.get_or_create(conn, "/docs/active2")

        # Disable f2
        cursor = conn.cursor()
        cursor.execute("UPDATE folders SET enabled = 0 WHERE id = ?;", (f2.id,))
        cursor.close()

    with db.connection() as conn:
        all_folders = FolderRepository.list_all(conn)
        active_folders = FolderRepository.list_active(conn)

    assert len(all_folders) == 3
    assert len(active_folders) == 2
    active_paths = {f.path for f in active_folders}
    assert not any("disabled" in p for p in active_paths)
    assert any("active1" in p for p in active_paths)
    assert any("active2" in p for p in active_paths)


