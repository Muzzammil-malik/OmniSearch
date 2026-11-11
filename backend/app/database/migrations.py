"""Versioned schema migrations for SQLite database."""

from datetime import datetime, timezone
import sqlite3
from typing import Callable, List, Tuple
from app.core.logging import get_logger

logger = get_logger(__name__)


def migration_v1(conn: sqlite3.Connection) -> None:
    """Initial Phase 3 schema: folders, files, chunks, index_jobs, and settings tables."""
    cursor = conn.cursor()

    # 1. Folders table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS folders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        path TEXT NOT NULL UNIQUE,
        enabled INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    """)

    # 2. Files table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS files (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        folder_id INTEGER REFERENCES folders(id) ON DELETE CASCADE,
        path TEXT NOT NULL UNIQUE,
        filename TEXT NOT NULL,
        extension TEXT NOT NULL,
        file_type TEXT NOT NULL,
        sha256 TEXT,
        size_bytes INTEGER NOT NULL DEFAULT 0,
        modified_at TEXT NOT NULL,
        indexed_at TEXT NOT NULL,
        status TEXT NOT NULL,
        error_message TEXT,
        metadata_json TEXT NOT NULL DEFAULT '{}'
    );
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_files_folder_id ON files(folder_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_files_sha256 ON files(sha256);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_files_status ON files(status);")

    # 3. Chunks table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS chunks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_id INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
        chunk_index INTEGER NOT NULL,
        source_segment_index INTEGER NOT NULL DEFAULT 0,
        content TEXT NOT NULL,
        token_count INTEGER NOT NULL DEFAULT 0,
        page_number INTEGER,
        slide_number INTEGER,
        sheet_name TEXT,
        row_number INTEGER,
        start_line INTEGER,
        end_line INTEGER,
        metadata_json TEXT NOT NULL DEFAULT '{}'
    );
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunks_file_chunk ON chunks(file_id, chunk_index);")

    # 4. Indexing Jobs table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS index_jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        status TEXT NOT NULL,
        total_files INTEGER NOT NULL DEFAULT 0,
        processed_files INTEGER NOT NULL DEFAULT 0,
        successful_files INTEGER NOT NULL DEFAULT 0,
        failed_files INTEGER NOT NULL DEFAULT 0,
        skipped_files INTEGER NOT NULL DEFAULT 0,
        started_at TEXT NOT NULL,
        finished_at TEXT,
        error_message TEXT
    );
    """)

    # 5. Application Settings table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    """)
    cursor.close()


def migration_v2(conn: sqlite3.Connection) -> None:
    """Phase 4 migration: SQLite FTS5 full-text search virtual table and automatic synchronization triggers."""
    cursor = conn.cursor()

    # 1. Dedicated FTS5 virtual table indexing chunk content, filename, and document title.
    # Indexed columns: content (col 0), filename (col 1), doc_title (col 2).
    # Unindexed columns: chunk_id (col 3), file_id (col 4).
    cursor.execute("""
    CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
        content,
        filename,
        doc_title,
        chunk_id UNINDEXED,
        file_id UNINDEXED,
        tokenize = 'unicode61'
    );
    """)

    # 2. Trigger on chunks INSERT: automatically index new chunk with file metadata
    cursor.execute("""
    CREATE TRIGGER IF NOT EXISTS trg_chunks_ai AFTER INSERT ON chunks
    BEGIN
        INSERT INTO chunks_fts(content, filename, doc_title, chunk_id, file_id)
        SELECT new.content,
               f.filename,
               COALESCE(json_extract(f.metadata_json, '$.title'), f.filename),
               new.id,
               new.file_id
        FROM files f WHERE f.id = new.file_id;
    END;
    """)

    # 3. Trigger on chunks DELETE: automatically remove deleted chunk from FTS
    cursor.execute("""
    CREATE TRIGGER IF NOT EXISTS trg_chunks_ad AFTER DELETE ON chunks
    BEGIN
        DELETE FROM chunks_fts WHERE chunk_id = old.id;
    END;
    """)

    # 4. Trigger on files DELETE: remove all associated chunk FTS records (covers CASCADE and direct deletes)
    cursor.execute("""
    CREATE TRIGGER IF NOT EXISTS trg_files_ad AFTER DELETE ON files
    BEGIN
        DELETE FROM chunks_fts WHERE file_id = old.id;
    END;
    """)

    # 5. Trigger on files UPDATE: update filename and doc_title in FTS when file metadata changes
    cursor.execute("""
    CREATE TRIGGER IF NOT EXISTS trg_files_au AFTER UPDATE OF filename, metadata_json ON files
    BEGIN
        UPDATE chunks_fts
        SET filename = new.filename,
            doc_title = COALESCE(json_extract(new.metadata_json, '$.title'), new.filename)
        WHERE file_id = old.id;
    END;
    """)

    # 6. Backfill existing chunks if any exist (e.g. from Phase 3 before Phase 4 migration)
    cursor.execute("""
    INSERT INTO chunks_fts (content, filename, doc_title, chunk_id, file_id)
    SELECT c.content,
           f.filename,
           COALESCE(json_extract(f.metadata_json, '$.title'), f.filename),
           c.id,
           c.file_id
    FROM chunks c
    JOIN files f ON c.file_id = f.id
    WHERE c.id NOT IN (SELECT chunk_id FROM chunks_fts);
    """)

    cursor.close()


def migration_v3(conn: sqlite3.Connection) -> None:
    """Phase 5 migration: chunk_embeddings table for tracking vector embedding metadata."""
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS chunk_embeddings (
        chunk_id INTEGER PRIMARY KEY REFERENCES chunks(id) ON DELETE CASCADE,
        file_id INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
        model_name TEXT NOT NULL,
        dimensions INTEGER NOT NULL,
        embedded_at TEXT NOT NULL
    );
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunk_embeddings_file_id ON chunk_embeddings(file_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunk_embeddings_model ON chunk_embeddings(model_name);")
    cursor.close()


# Ordered migration registry: (version, name, migration_function)
MIGRATIONS: List[Tuple[int, str, Callable[[sqlite3.Connection], None]]] = [
    (1, "001_initial_schema", migration_v1),
    (2, "002_fts5_search", migration_v2),
    (3, "003_semantic_embeddings", migration_v3),
]


def apply_migrations(conn: sqlite3.Connection) -> int:
    """Apply all pending migrations to the connected SQLite database in version sequence.

    Args:
        conn: Open SQLite connection.

    Returns:
        Highest migration version applied.
    """
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS schema_migrations (
        version INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        applied_at TEXT NOT NULL
    );
    """)

    # Ensure schema_migrations table has the 'name' column even if created by an interim schema definition
    cursor.execute("PRAGMA table_info(schema_migrations);")
    existing_cols = {row[1] for row in cursor.fetchall()}
    if "name" not in existing_cols:
        cursor.execute("ALTER TABLE schema_migrations ADD COLUMN name TEXT NOT NULL DEFAULT '';")

    cursor.execute("SELECT version FROM schema_migrations ORDER BY version ASC;")
    applied_versions = {row[0] for row in cursor.fetchall()}

    applied_count = 0
    highest_version = max(applied_versions) if applied_versions else 0

    for version, name, migration_fn in MIGRATIONS:
        if version not in applied_versions:
            logger.info("Applying database schema migration v%d (%s)...", version, name)
            migration_fn(conn)
            now_iso = datetime.now(timezone.utc).isoformat()
            cursor.execute(
                "INSERT INTO schema_migrations (version, name, applied_at) VALUES (?, ?, ?);",
                (version, name, now_iso),
            )
            applied_count += 1
            highest_version = version

    cursor.close()
    if applied_count > 0:
        conn.commit()
        logger.info("Successfully applied %d migration(s). Current schema version: v%d", applied_count, highest_version)
    return highest_version

