"""Automated unit and integration tests for the Phase 10.5 Embedding Cache & Deduplication."""

import hashlib
from pathlib import Path
import pytest
from PIL import Image

from app.database.connection import DatabaseConnectionManager
from app.database.initialization import init_db
from app.database.repositories.cache import EmbeddingCacheRepository
from app.database.repositories.files import FileRepository
from app.database.repositories.folders import FolderRepository
from app.embeddings.test_embedder import DeterministicTestEmbedder
from app.services.indexer import IndexingService
from app.services.semantic_pipeline import SemanticPipeline
from app.vector_store.chroma import ChromaVectorStore


class CountingTestEmbedder(DeterministicTestEmbedder):
    """Test embedder that tracks how many times model inference is actually invoked."""

    def __init__(self, dimension: int = 768, model_id: str = "google/embeddinggemma-2-test"):
        super().__init__(dimension=dimension, model_id=model_id)
        self.doc_embed_calls = 0
        self.image_embed_calls = 0
        self.audio_embed_calls = 0
        self.video_embed_calls = 0

    def embed_documents(self, documents, titles=None):
        self.doc_embed_calls += len(documents)
        return super().embed_documents(documents, titles=titles)

    def embed_image(self, image_path: str):
        self.image_embed_calls += 1
        return super().embed_image(image_path)

    def embed_audio(self, audio_path: str):
        self.audio_embed_calls += 1
        return super().embed_audio(audio_path)

    def embed_video(self, video_path: str):
        self.video_embed_calls += 1
        return super().embed_video(video_path)


def test_embedding_cache_repository_crud(tmp_path: Path):
    """Verify EmbeddingCacheRepository stores, fetches, and serializes vectors correctly."""
    db_file = tmp_path / "cache_test.db"
    db = init_db(db_file)

    test_vec = [float(i) / 100.0 for i in range(768)]
    content_sha = hashlib.sha256(b"sample content").hexdigest()
    cache_key = EmbeddingCacheRepository.compute_cache_key(
        content_sha256=content_sha,
        model_name="google/embeddinggemma-2",
        modality="text",
        dimensions=768,
    )

    with db.connection() as conn:
        assert EmbeddingCacheRepository.get(conn, cache_key) is None
        EmbeddingCacheRepository.put(
            conn=conn,
            cache_key=cache_key,
            content_sha256=content_sha,
            model_name="google/embeddinggemma-2",
            modality="text",
            dimensions=768,
            vector=test_vec,
        )

        fetched = EmbeddingCacheRepository.get(conn, cache_key)
        assert fetched is not None
        assert len(fetched) == 768
        assert pytest.approx(fetched[0], abs=1e-5) == test_vec[0]
        assert pytest.approx(fetched[100], abs=1e-5) == test_vec[100]

        # Batch lookup
        batch = EmbeddingCacheRepository.get_batch(conn, [cache_key, "nonexistent_key"])
        assert cache_key in batch
        assert len(batch[cache_key]) == 768
        assert "nonexistent_key" not in batch


def test_cache_reused_on_reindexing(tmp_path: Path):
    """Verify unchanged content hits cache and skips model inference on subsequent index runs."""
    db_file = tmp_path / "reuse_test.db"
    vectors_dir = tmp_path / "reuse_vectors"
    library_dir = tmp_path / "reuse_lib"
    library_dir.mkdir()

    # Create 1 text file and 1 image
    txt_path = library_dir / "article.txt"
    txt_path.write_text("Optimized vector caching dramatically improves ingestion throughput.", encoding="utf-8")
    img_path = library_dir / "photo.png"
    img = Image.new("RGB", (100, 100), color=(10, 20, 30))
    img.save(img_path)

    db = init_db(db_file)
    vector_store = ChromaVectorStore(persist_dir=vectors_dir)
    embedder = CountingTestEmbedder(dimension=768)
    pipeline = SemanticPipeline(db=db, embedder=embedder, vector_store=vector_store)
    indexer = IndexingService(db=db, semantic_pipeline=pipeline)

    with db.connection() as conn:
        FolderRepository.get_or_create(conn, str(library_dir))

    # First index run: cold cache -> model must be invoked
    job1 = indexer.index_folder(library_dir, generate_embeddings=True)
    assert job1.status == "completed"
    assert embedder.doc_embed_calls == 1
    assert embedder.image_embed_calls == 1

    with db.connection() as conn:
        assert EmbeddingCacheRepository.count(conn) == 2

    # Reset call counters
    embedder.doc_embed_calls = 0
    embedder.image_embed_calls = 0

    # Force reindex with force_reindex=True (simulates re-extracting and re-syncing)
    # Even when re-indexing, identical content MUST hit the cache and avoid model inference!
    with db.transaction() as conn:
        # Delete chunk_embeddings tracking to simulate unembedded chunks needing sync
        conn.execute("DELETE FROM chunk_embeddings;")

    embedded_again = pipeline.sync_embeddings()
    assert embedded_again == 2

    # Model inference was NOT called because all vectors were resolved from cache!
    assert embedder.doc_embed_calls == 0
    assert embedder.image_embed_calls == 0


def test_modified_content_generates_new_embedding(tmp_path: Path):
    """Verify modifying file content changes cache key and triggers new embedding."""
    db_file = tmp_path / "mod_test.db"
    vectors_dir = tmp_path / "mod_vectors"
    library_dir = tmp_path / "mod_lib"
    library_dir.mkdir()

    txt_path = library_dir / "notes.txt"
    txt_path.write_text("Original paragraph content.", encoding="utf-8")

    db = init_db(db_file)
    vector_store = ChromaVectorStore(persist_dir=vectors_dir)
    embedder = CountingTestEmbedder(dimension=768)
    pipeline = SemanticPipeline(db=db, embedder=embedder, vector_store=vector_store)
    indexer = IndexingService(db=db, semantic_pipeline=pipeline)

    with db.connection() as conn:
        FolderRepository.get_or_create(conn, str(library_dir))

    indexer.index_folder(library_dir, generate_embeddings=True)
    assert embedder.doc_embed_calls == 1

    # Modify content
    txt_path.write_text("Completely revised text about machine learning systems.", encoding="utf-8")
    embedder.doc_embed_calls = 0

    indexer.index_folder(library_dir, generate_embeddings=True)
    # Modified content missed cache -> model was invoked for new content
    assert embedder.doc_embed_calls == 1

    with db.connection() as conn:
        # Both original and new embeddings are preserved in content-addressed cache
        assert EmbeddingCacheRepository.count(conn) == 2


def test_config_change_invalidates_cache(tmp_path: Path):
    """Verify changing model identity or dimension produces distinct cache keys."""
    sha = hashlib.sha256(b"same text").hexdigest()
    k1 = EmbeddingCacheRepository.compute_cache_key(sha, "google/embeddinggemma-2", "text", 768, pipeline_version=1)
    k2 = EmbeddingCacheRepository.compute_cache_key(sha, "google/embeddinggemma-2", "text", 512, pipeline_version=1)
    k3 = EmbeddingCacheRepository.compute_cache_key(sha, "google/embeddinggemma-3", "text", 768, pipeline_version=1)
    k4 = EmbeddingCacheRepository.compute_cache_key(sha, "google/embeddinggemma-2", "text", 768, pipeline_version=2)

    assert k1 != k2
    assert k1 != k3
    assert k1 != k4

