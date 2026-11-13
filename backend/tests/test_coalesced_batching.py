"""Automated tests for Optimization A: Coalesced Cross-File Embedding Batching.

Verifies:
- Test 1: Multiple files with small numbers of chunks are combined into embedding batches.
- Test 2: Batch size remains capped at the configured value (e.g., 16).
- Test 3: Chunk IDs and metadata remain correct.
- Test 4: Embedding provenance remains correct in SQLite chunk_embeddings.
- Test 5: Existing single-file indexing behavior still works.
- Test 6: Existing non-semantic indexing still works (generate_embeddings=False).
- Test 7: No duplicate embeddings are created.
- Test 8: Already-embedded chunks are not unnecessarily regenerated.
"""

from pathlib import Path
from typing import List, Optional
import pytest

from app.database.connection import DatabaseConnectionManager
from app.database.migrations import apply_migrations
from app.database.repositories.chunks import ChunkRepository
from app.database.repositories.embeddings import ChunkEmbeddingRepository
from app.database.repositories.files import FileRepository
from app.database.repositories.folders import FolderRepository
from app.embeddings.test_embedder import DeterministicTestEmbedder
from app.services.indexer import IndexingService
from app.services.semantic_pipeline import SemanticPipeline
from app.vector_store.chroma import ChromaVectorStore


class RecordingTestEmbedder(DeterministicTestEmbedder):
    """Test embedder that records batch sizes of all embed_documents calls."""

    def __init__(self, dimension: int = 768) -> None:
        super().__init__(dimension=dimension)
        self.recorded_batches: List[List[str]] = []

    def embed_documents(
        self,
        documents: List[str],
        titles: Optional[List[Optional[str]]] = None,
    ) -> List[List[float]]:
        self.recorded_batches.append(list(documents))
        return super().embed_documents(documents, titles=titles)


@pytest.fixture
def batching_env(tmp_path: Path):
    """Set up an isolated database, vector store, and IndexingService with RecordingTestEmbedder."""
    db_file = tmp_path / "test_batching.db"
    db = DatabaseConnectionManager(db_path=db_file)
    with db.connection() as conn:
        apply_migrations(conn)

    vectors_dir = tmp_path / "vectors"
    vectors_dir.mkdir(parents=True, exist_ok=True)
    vector_store = ChromaVectorStore(persist_dir=str(vectors_dir))

    embedder = RecordingTestEmbedder(dimension=768)
    semantic_pipeline = SemanticPipeline(
        db=db,
        embedder=embedder,
        vector_store=vector_store,
        batch_size=16,
        fetch_pool_size=16,
    )
    indexer = IndexingService(db=db, semantic_pipeline=semantic_pipeline)

    # Register root test folder
    with db.transaction() as conn:
        folder = FolderRepository.get_or_create(conn, str(tmp_path))
        folder_id = folder.id

    return {
        "db": db,
        "indexer": indexer,
        "pipeline": semantic_pipeline,
        "embedder": embedder,
        "vector_store": vector_store,
        "tmp_path": tmp_path,
        "folder_id": folder_id,
    }


def _create_test_file(path: Path, identifier: int = 0) -> Path:
    """Create a single text file that represents one chunk."""
    content = (
        f"File identifier {identifier}: This is chunk content for testing coalesced embedding batching. "
        f"OmniSearch local-first indexing groups small files into optimal batches."
    )
    path.write_text(content, encoding="utf-8")
    return path


def test_coalesced_batching_multiple_files_combined(batching_env):
    """Test 1: Multiple files with small numbers of chunks are combined into a single embedding batch."""
    indexer = batching_env["indexer"]
    embedder = batching_env["embedder"]
    tmp_path = batching_env["tmp_path"]
    folder_id = batching_env["folder_id"]

    # Create 12 files (each is 1 chunk) -> fits into 1 batch of 16
    files = [_create_test_file(tmp_path / f"file_{i}.txt", i) for i in range(12)]

    records = indexer.index_files(files, folder_id=folder_id, generate_embeddings=True)
    assert len(records) == 12
    assert all(r is not None and r.status == "success" for r in records)

    # All 12 chunks must be embedded in a single batch rather than 12 separate calls
    assert len(embedder.recorded_batches) == 1
    assert len(embedder.recorded_batches[0]) == 12


def test_batch_size_capped_at_configured_limit(batching_env):
    """Test 2: Batch size remains capped at configured batch_size=16."""
    indexer = batching_env["indexer"]
    embedder = batching_env["embedder"]
    tmp_path = batching_env["tmp_path"]
    folder_id = batching_env["folder_id"]

    # Create 22 files (22 chunks total)
    files = [_create_test_file(tmp_path / f"large_file_{i}.txt", i) for i in range(22)]

    records = indexer.index_files(files, folder_id=folder_id, generate_embeddings=True)
    assert len(records) == 22

    # 22 chunks with batch_size=16 should produce 2 batches: batch 1 of 16, batch 2 of 6
    assert len(embedder.recorded_batches) == 2
    assert len(embedder.recorded_batches[0]) == 16
    assert len(embedder.recorded_batches[1]) == 6


def test_chunk_ids_and_metadata_preserved(batching_env):
    """Test 3: Chunk IDs and metadata remain correct across files in coalesced batches."""
    indexer = batching_env["indexer"]
    db = batching_env["db"]
    vector_store = batching_env["vector_store"]
    tmp_path = batching_env["tmp_path"]
    folder_id = batching_env["folder_id"]

    files = [_create_test_file(tmp_path / f"meta_file_{i}.txt", i) for i in range(5)]
    indexer.index_files(files, folder_id=folder_id, generate_embeddings=True)

    with db.connection() as conn:
        unembedded = ChunkEmbeddingRepository.get_unembedded_chunks(conn, limit=100)
        assert len(unembedded) == 0  # None unembedded

        file_recs = FileRepository.list_by_folder(conn, folder_id)
        assert len(file_recs) == 5

    # Vector store count must be 5
    assert vector_store.count() == 5


def test_embedding_provenance_correct(batching_env):
    """Test 4: Embedding provenance is recorded correctly in SQLite chunk_embeddings."""
    indexer = batching_env["indexer"]
    db = batching_env["db"]
    tmp_path = batching_env["tmp_path"]
    folder_id = batching_env["folder_id"]

    files = [_create_test_file(tmp_path / f"prov_file_{i}.txt", i) for i in range(4)]
    indexer.index_files(files, folder_id=folder_id, generate_embeddings=True)

    with db.connection() as conn:
        count_prov = ChunkEmbeddingRepository.count_embedded(conn)
        total_chunks = ChunkRepository.count_total(conn)
        assert count_prov == 4
        assert total_chunks == 4


def test_single_file_indexing_still_works(batching_env):
    """Test 5: Existing single-file indexing behavior still works seamlessly."""
    indexer = batching_env["indexer"]
    embedder = batching_env["embedder"]
    tmp_path = batching_env["tmp_path"]
    folder_id = batching_env["folder_id"]

    f = _create_test_file(tmp_path / "single_file.txt", 1)
    rec = indexer.index_single_file(f, folder_id=folder_id, generate_embeddings=True)
    assert rec is not None
    assert rec.status == "success"

    assert len(embedder.recorded_batches) == 1
    assert len(embedder.recorded_batches[0]) == 1


def test_non_semantic_indexing_still_works(batching_env):
    """Test 6: Existing non-semantic indexing still works (generate_embeddings=False)."""
    indexer = batching_env["indexer"]
    embedder = batching_env["embedder"]
    db = batching_env["db"]
    tmp_path = batching_env["tmp_path"]
    folder_id = batching_env["folder_id"]

    files = [_create_test_file(tmp_path / f"nosem_{i}.txt", i) for i in range(3)]
    records = indexer.index_files(files, folder_id=folder_id, generate_embeddings=False)
    assert len(records) == 3

    # Zero embeddings generated
    assert len(embedder.recorded_batches) == 0

    with db.connection() as conn:
        unembedded = ChunkEmbeddingRepository.count_unembedded(conn)
        assert unembedded == 3


def test_no_duplicate_embeddings_created(batching_env):
    """Test 7: Re-indexing or re-syncing does not create duplicate embeddings."""
    indexer = batching_env["indexer"]
    pipeline = batching_env["pipeline"]
    embedder = batching_env["embedder"]
    db = batching_env["db"]
    tmp_path = batching_env["tmp_path"]
    folder_id = batching_env["folder_id"]

    files = [_create_test_file(tmp_path / f"nodup_{i}.txt", i) for i in range(3)]
    indexer.index_files(files, folder_id=folder_id, generate_embeddings=True)

    batches_count_first = len(embedder.recorded_batches)
    assert batches_count_first == 1

    # Second sync pass should find 0 unembedded chunks
    new_embedded = pipeline.sync_embeddings()
    assert new_embedded == 0
    assert len(embedder.recorded_batches) == batches_count_first

    with db.connection() as conn:
        assert ChunkEmbeddingRepository.count_embedded(conn) == 3


def test_already_embedded_chunks_not_regenerated(batching_env):
    """Test 8: Already-embedded chunks are skipped; only new file chunks are embedded."""
    indexer = batching_env["indexer"]
    embedder = batching_env["embedder"]
    tmp_path = batching_env["tmp_path"]
    folder_id = batching_env["folder_id"]

    # File 1 has 1 chunk
    f1 = _create_test_file(tmp_path / "existing.txt", 1)
    indexer.index_single_file(f1, folder_id=folder_id, generate_embeddings=True)
    assert len(embedder.recorded_batches) == 1
    assert len(embedder.recorded_batches[0]) == 1

    # Now index File 2 with 1 chunk using coalesced index_files
    f2 = _create_test_file(tmp_path / "new_file.txt", 2)
    indexer.index_files([f1, f2], folder_id=folder_id, generate_embeddings=True)

    # Embedder should have only processed 1 new chunk from f2
    assert len(embedder.recorded_batches) == 2
    assert len(embedder.recorded_batches[1]) == 1
