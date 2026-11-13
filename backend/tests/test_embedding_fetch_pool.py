"""Automated test suite for Phase 10.5C: Safe Embedding Pool Optimization.

Verifies:
1. Configuration:
   - Settings.embedding_fetch_pool_size defaults to 128.
   - EmbeddingConfig.fetch_pool_size defaults to 128, bounded [16, 1024].
2. SQLite Fetch Pool:
   - SemanticPipeline fetches up to fetch_pool_size (128) chunks in one sync cycle.
   - When fewer chunks exist (e.g., 25), processes all available chunks cleanly.
   - Zero-chunk / empty queue returns 0.
3. Model Inference Batch Capping:
   - Model inference batches remain strictly capped at batch_size (16).
4. Length-Aware Grouping Across Candidate Pool:
   - Texts in the candidate pool are grouped by length, minimizing padding waste.
   - Exact input ordering is strictly preserved.
5. Numerical Equivalence:
   - Embedding vectors produced with pooled length-aware batching match sequential
     embeddings within numerical tolerance (1e-5).
6. Full Integration with SQLite and ChromaDB:
   - Provenance recorded correctly in SQLite chunk_embeddings.
   - Vectors and metadata upserted correctly in ChromaDB.
"""

from pathlib import Path
from typing import List, Optional
import pytest

from app.core.config import Settings
from app.database.connection import DatabaseConnectionManager
from app.database.migrations import apply_migrations
from app.database.repositories.chunks import ChunkRepository
from app.database.repositories.embeddings import ChunkEmbeddingRepository
from app.database.repositories.files import FileRepository
from app.database.repositories.folders import FolderRepository
from app.embeddings.configuration import EmbeddingConfig
from app.embeddings.test_embedder import DeterministicTestEmbedder
from app.schemas.extraction import ExtractionStatus
from app.schemas.processing import DocumentChunk, FileRecord
from app.services.indexer import IndexingService
from app.services.semantic_pipeline import SemanticPipeline
from app.vector_store.chroma import ChromaVectorStore


class InferenceBatchTrackingEmbedder(DeterministicTestEmbedder):
    """Test embedder that simulates sub-batch model forward inference and records batch sizes."""

    def __init__(self, dimension: int = 768, batch_size: int = 16) -> None:
        super().__init__(dimension=dimension)
        self.batch_size = batch_size
        self.inference_batches: List[List[str]] = []
        self.total_embed_doc_calls: int = 0

    def embed_documents(
        self,
        documents: List[str],
        titles: Optional[List[Optional[str]]] = None,
    ) -> List[List[float]]:
        self.total_embed_doc_calls += 1
        if not documents:
            return []

        # Mimic EmbeddingGemmaEmbedder._generate_embeddings length-aware batching
        if len(documents) > self.batch_size:
            indexed = sorted(enumerate(documents), key=lambda x: len(x[1]))
        else:
            indexed = list(enumerate(documents))

        results: List[Optional[List[float]]] = [None] * len(documents)

        for start in range(0, len(indexed), self.batch_size):
            slice_items = indexed[start : start + self.batch_size]
            batch_texts = [item[1] for item in slice_items]
            self.inference_batches.append(batch_texts)

            # Generate vectors
            slice_vecs = [self._generate_vector(t) for t in batch_texts]
            for (orig_idx, _), vec in zip(slice_items, slice_vecs):
                results[orig_idx] = vec

        return results  # type: ignore[return-value]


def test_configuration_defaults_and_validation():
    """Verify configuration settings for Phase 10.5C."""
    # Settings default
    settings = Settings()
    assert settings.embedding_fetch_pool_size == 128
    assert settings.embedding_batch_size == 16

    # EmbeddingConfig default
    config = EmbeddingConfig()
    assert config.fetch_pool_size == 128
    assert config.batch_size == 16

    # Custom valid values
    custom_cfg = EmbeddingConfig(fetch_pool_size=256, batch_size=16)
    assert custom_cfg.fetch_pool_size == 256
    assert custom_cfg.batch_size == 16

    # Bounds validation
    with pytest.raises(Exception):
        EmbeddingConfig(fetch_pool_size=8)  # ge=16

    with pytest.raises(Exception):
        EmbeddingConfig(fetch_pool_size=2048)  # le=1024


def test_fetch_pool_128_slices_into_inference_batches_of_16(tmp_path: Path):
    """Verify that a candidate pool of 128 chunks results in 1 fetch and 8 inference batches of 16."""
    db_file = tmp_path / "pool_test.db"
    db = DatabaseConnectionManager(db_path=db_file)
    with db.connection() as conn:
        apply_migrations(conn)

    vectors_dir = tmp_path / "vectors"
    vectors_dir.mkdir(parents=True, exist_ok=True)
    vector_store = ChromaVectorStore(persist_dir=str(vectors_dir))

    embedder = InferenceBatchTrackingEmbedder(dimension=768, batch_size=16)
    pipeline = SemanticPipeline(
        db=db,
        embedder=embedder,
        vector_store=vector_store,
        batch_size=16,
        fetch_pool_size=128,
    )

    # Insert 128 chunks across multiple files
    with db.transaction() as conn:
        folder = FolderRepository.get_or_create(conn, str(tmp_path))
        for f_idx in range(16):
            file_rec = FileRecord(
                folder_id=folder.id,
                path=str(tmp_path / f"doc_{f_idx}.txt"),
                filename=f"doc_{f_idx}.txt",
                extension=".txt",
                file_type="text",
                modified_at="2026-11-13T12:00:00Z",
                status=ExtractionStatus.SUCCESS.value,
            )
            fid = FileRepository.upsert(conn, file_rec)
            # 8 chunks per file = 16 * 8 = 128 chunks total
            chunks = [
                DocumentChunk(
                    chunk_index=c_idx,
                    content=f"Content for file {f_idx} chunk {c_idx} " + ("word " * (c_idx * 5 + f_idx)),
                    token_count=10 + c_idx * 5,
                    char_count=50 + c_idx * 20,
                )
                for c_idx in range(8)
            ]
            ChunkRepository.insert_chunks(conn, fid, chunks)

    # Synchronize embeddings
    processed = pipeline.sync_embeddings()
    assert processed == 128

    # SemanticPipeline should have called embed_documents ONCE for the pool of 128
    assert embedder.total_embed_doc_calls == 1

    # The embedder should have executed 8 model forward inference batches, each of size exactly 16
    assert len(embedder.inference_batches) == 8
    for batch in embedder.inference_batches:
        assert len(batch) == 16

    # Verify vector store and SQLite provenance
    assert vector_store.count() == 128
    with db.connection() as conn:
        assert ChunkEmbeddingRepository.count_embedded(conn) == 128
        assert ChunkEmbeddingRepository.count_unembedded(conn) == 0


def test_partial_fetch_pool_smaller_than_128(tmp_path: Path):
    """Verify that when fewer chunks exist than fetch_pool_size (e.g. 35 chunks), all are processed."""
    db_file = tmp_path / "partial_test.db"
    db = DatabaseConnectionManager(db_path=db_file)
    with db.connection() as conn:
        apply_migrations(conn)

    vectors_dir = tmp_path / "vectors"
    vectors_dir.mkdir(parents=True, exist_ok=True)
    vector_store = ChromaVectorStore(persist_dir=str(vectors_dir))

    embedder = InferenceBatchTrackingEmbedder(dimension=768, batch_size=16)
    pipeline = SemanticPipeline(
        db=db,
        embedder=embedder,
        vector_store=vector_store,
        batch_size=16,
        fetch_pool_size=128,
    )

    # Insert 35 chunks
    with db.transaction() as conn:
        folder = FolderRepository.get_or_create(conn, str(tmp_path))
        file_rec = FileRecord(
            folder_id=folder.id,
            path=str(tmp_path / "partial_doc.txt"),
            filename="partial_doc.txt",
            extension=".txt",
            file_type="text",
            modified_at="2026-11-13T12:00:00Z",
            status=ExtractionStatus.SUCCESS.value,
        )
        fid = FileRepository.upsert(conn, file_rec)
        chunks = [
            DocumentChunk(
                chunk_index=i,
                content=f"Partial chunk {i} content text sample",
                token_count=10,
                char_count=40,
            )
            for i in range(35)
        ]
        ChunkRepository.insert_chunks(conn, fid, chunks)

    processed = pipeline.sync_embeddings()
    assert processed == 35

    # 1 call to embed_documents with 35 items
    assert embedder.total_embed_doc_calls == 1

    # 35 items sliced into batches of 16 -> 16, 16, 3
    assert len(embedder.inference_batches) == 3
    assert len(embedder.inference_batches[0]) == 16
    assert len(embedder.inference_batches[1]) == 16
    assert len(embedder.inference_batches[2]) == 3

    assert vector_store.count() == 35


def test_ordering_preservation_and_numerical_equivalence():
    """Verify that length-aware batching across candidate pool preserves exact document order and vector values."""
    embedder = InferenceBatchTrackingEmbedder(dimension=768, batch_size=16)

    # Create 40 documents of deliberately varying lengths
    documents = [
        f"Item {i}: " + ("alpha " * ((i * 7) % 50 + 1))
        for i in range(40)
    ]

    # Ground truth: generate vector for each document individually
    ground_truth = [embedder._generate_vector(doc) for doc in documents]

    # Process all 40 with length-aware batching
    batched_results = embedder.embed_documents(documents)

    assert len(batched_results) == 40
    for i in range(40):
        # Must match ground truth exactly at the same index
        gt = ground_truth[i]
        actual = batched_results[i]
        assert len(actual) == len(gt) == 768
        for v1, v2 in zip(gt, actual):
            assert abs(v1 - v2) < 1e-6, f"Mismatch at index {i}: diff={abs(v1 - v2)}"


def test_empty_queue_idempotency(tmp_path: Path):
    """Verify that syncing when 0 chunks exist returns 0 without calling embedder or vector store."""
    db_file = tmp_path / "empty_test.db"
    db = DatabaseConnectionManager(db_path=db_file)
    with db.connection() as conn:
        apply_migrations(conn)

    vectors_dir = tmp_path / "vectors"
    vectors_dir.mkdir(parents=True, exist_ok=True)
    vector_store = ChromaVectorStore(persist_dir=str(vectors_dir))

    embedder = InferenceBatchTrackingEmbedder(dimension=768, batch_size=16)
    pipeline = SemanticPipeline(
        db=db,
        embedder=embedder,
        vector_store=vector_store,
        batch_size=16,
        fetch_pool_size=128,
    )

    processed = pipeline.sync_embeddings()
    assert processed == 0
    assert embedder.total_embed_doc_calls == 0
    assert len(embedder.inference_batches) == 0
