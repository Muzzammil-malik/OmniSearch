"""End-to-End verification script for Phase 2 Native Dependency & Reliability Remediation.

Verifies:
1. Health and System Status endpoints.
2. Real EmbeddingGemma 2 inference on CPU (text prompt -> 768-d unit vector).
3. Real vector persistence in ChromaDB.
4. Real semantic search execution.
5. Real hybrid search with RRF fusion.
6. Repeated same-process queries verifying absence of memory or state corruption.
"""

import math
import sys
import tempfile
import time
from pathlib import Path

# Add backend to sys.path
backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient
from app.core.config import get_settings
from app.database.connection import DatabaseConnectionManager
from app.database.migrations import apply_migrations
from app.database.repositories.chunks import ChunkRepository
from app.database.repositories.embeddings import ChunkEmbeddingRepository
from app.database.repositories.files import FileRepository
from app.database.repositories.folders import FolderRepository
from app.embeddings.configuration import EmbeddingConfig
from app.embeddings.embedder import EmbeddingGemmaEmbedder
from app.main import create_app
from app.schemas.extraction import ExtractionStatus
from app.schemas.processing import DocumentChunk, FileRecord
from app.schemas.search import HybridSearchQuery
from app.search.hybrid_search import HybridSearchEngine
from app.search.keyword_search import KeywordSearchEngine
from app.search.semantic_search import SemanticSearchEngine
from app.vector_store.chroma import ChromaVectorStore


def main():
    print("=" * 70)
    print("OmniSearch Phase 2 — Real End-to-End Remediation Verification")
    print("=" * 70)

    # -------------------------------------------------------------
    # 1. Health & System Status API Verification
    # -------------------------------------------------------------
    print("\n[1/6] Testing Health & System Status endpoints...")
    app = create_app()
    client = TestClient(app)

    health_resp = client.get("/api/v1/health")
    assert health_resp.status_code == 200, f"Health check failed: {health_resp.text}"
    health_data = health_resp.json()
    print(f"  ✓ Health status: {health_data['status']} (version: {health_data['version']})")

    status_resp = client.get("/api/v1/system/status")
    assert status_resp.status_code == 200, f"System status check failed: {status_resp.text}"
    status_data = status_resp.json()
    print(f"  ✓ System status:")
    print(f"      - App: {status_data['app_name']} v{status_data['version']}")
    print(f"      - Vector Store: status={status_data['vector_store']['status']}, error={status_data['vector_store']['error_category']}")
    print(f"      - Embedding Model: status={status_data['embedding_model']['status']}, model_id={status_data['embedding_model']['model_id']}")

    # -------------------------------------------------------------
    # 2. Real EmbeddingGemma 2 Inference on CPU
    # -------------------------------------------------------------
    print("\n[2/6] Testing real EmbeddingGemma 2 inference on CPU...")
    settings = get_settings()
    model_path = settings.resolved_embedding_model

    config = EmbeddingConfig(
        model_id=model_path,
        dimension=768,
        batch_size=4,
        device="cpu",
        precision="float32",
        local_files_only=True,
    )

    t0 = time.perf_counter()
    embedder = EmbeddingGemmaEmbedder(config=config)

    test_docs = [
        "OmniSearch local-first desktop multifile search application architecture.",
        "Python FastAPI backend with SQLite full-text search and ChromaDB vectors.",
    ]
    doc_vectors = embedder.embed_documents(test_docs, titles=["Architecture Overview", "Tech Stack"])
    t_docs = time.perf_counter() - t0

    assert len(doc_vectors) == 2
    for i, vec in enumerate(doc_vectors):
        assert len(vec) == 768, f"Expected 768 dims, got {len(vec)}"
        assert all(math.isfinite(x) for x in vec), "Embedding vector contains non-finite numbers!"
        norm = math.sqrt(sum(x * x for x in vec))
        assert abs(norm - 1.0) < 1e-3, f"Vector not L2 normalized: {norm}"
        print(f"  ✓ Document {i+1} embedded: shape=({len(vec)},), norm={norm:.4f}")
    print(f"  ✓ Embedding documents took {t_docs:.2f}s on CPU")

    t0 = time.perf_counter()
    query_vec = embedder.embed_query("desktop local search architecture")
    t_query = time.perf_counter() - t0
    assert len(query_vec) == 768
    q_norm = math.sqrt(sum(x * x for x in query_vec))
    assert abs(q_norm - 1.0) < 1e-3
    print(f"  ✓ Query embedded: shape=({len(query_vec)},), norm={q_norm:.4f} ({t_query:.2f}s)")

    # -------------------------------------------------------------
    # 3. Real Vector Persistence & SQLite Synchronization
    # -------------------------------------------------------------
    print("\n[3/6] Testing real vector persistence in ChromaDB...")
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
        tmp_path = Path(tmp_dir)
        db_file = tmp_path / "e2e_test.db"
        chroma_dir = tmp_path / "chroma_vectors"

        db = DatabaseConnectionManager(db_path=db_file)
        with db.transaction() as conn:
            apply_migrations(conn)

        vector_store = ChromaVectorStore(persist_dir=chroma_dir, collection_name="e2e_verification")
        assert vector_store.is_available()

        # Insert records into SQLite
        with db.transaction() as conn:
            folder = FolderRepository.get_or_create(conn, str(tmp_path / "test_folder"))
            file_rec = FileRecord(
                folder_id=folder.id,
                path=str(tmp_path / "test_folder" / "architecture.txt"),
                filename="architecture.txt",
                extension=".txt",
                file_type="text",
                content_type="document",
                sha256="test_sha256_hash",
                size_bytes=1024,
                modified_at="2026-11-11T12:00:00Z",
                status=ExtractionStatus.SUCCESS.value,
            )
            file_id = FileRepository.upsert(conn, file_rec)

            chunk1 = DocumentChunk(
                chunk_index=0,
                content=test_docs[0],
                token_count=15,
                char_count=len(test_docs[0]),
            )
            chunk2 = DocumentChunk(
                chunk_index=1,
                content=test_docs[1],
                token_count=15,
                char_count=len(test_docs[1]),
            )
            ChunkRepository.insert_chunks(conn, file_id, [chunk1, chunk2])
            chunk_ids = [c.id for c in ChunkRepository.get_by_file_id(conn, file_id)]

        # Store in ChromaDB
        metadatas = [
            {"file_id": file_id, "chunk_index": 0, "filename": "architecture.txt", "file_type": "text", "content_type": "document", "folder_id": folder.id, "path": str(tmp_path / "test_folder" / "architecture.txt")},
            {"file_id": file_id, "chunk_index": 1, "filename": "architecture.txt", "file_type": "text", "content_type": "document", "folder_id": folder.id, "path": str(tmp_path / "test_folder" / "architecture.txt")},
        ]
        vector_store.upsert(
            chunk_ids=chunk_ids,
            embeddings=doc_vectors,
            documents=test_docs,
            metadatas=metadatas,
        )

        with db.transaction() as conn:
            records = [(cid, file_id, config.model_id, config.dimension) for cid in chunk_ids]
            ChunkEmbeddingRepository.record_batch(conn, records)

        count = vector_store.count()
        assert count == 2, f"Expected 2 vectors in Chroma, got {count}"
        print(f"  ✓ Successfully stored and verified {count} vectors in ChromaDB")

        # -------------------------------------------------------------
        # 4. Real Semantic Search Verification
        # -------------------------------------------------------------
        print("\n[4/6] Testing real semantic search...")
        sem_engine = SemanticSearchEngine(db=db, vector_store=vector_store, embedder=embedder)
        sem_res = sem_engine.search("desktop local search architecture", limit=5)
        assert sem_res.total_results >= 1, "Semantic search returned 0 results"
        top_sem = sem_res.results[0]
        print(f"  ✓ Top semantic result: '{top_sem.filename}' chunk #{top_sem.chunk_index}")
        print(f"      - Score: {top_sem.score:.4f}, Cosine Similarity: {top_sem.cosine_similarity:.4f}")
        assert top_sem.cosine_similarity > 0.0

        # -------------------------------------------------------------
        # 5. Real Hybrid Search Verification
        # -------------------------------------------------------------
        print("\n[5/6] Testing real hybrid search with RRF...")
        kw_engine = KeywordSearchEngine(db=db)
        hybrid_engine = HybridSearchEngine(
            db=db,
            keyword_engine=kw_engine,
            semantic_engine=sem_engine,
            use_concurrency=True,
        )

        hybrid_query = HybridSearchQuery(query="OmniSearch architecture", limit=5)
        hybrid_res = hybrid_engine.search(hybrid_query)
        assert hybrid_res.total_results >= 1
        assert hybrid_res.search_mode == "hybrid"
        assert hybrid_res.keyword_available is True
        assert hybrid_res.semantic_available is True
        top_hybrid = hybrid_res.results[0]
        print(f"  ✓ Hybrid search result: '{top_hybrid.filename}' (RRF score: {top_hybrid.rrf_score:.4f})")
        print(f"      - Keyword rank: {top_hybrid.keyword_rank}, Semantic rank: {top_hybrid.semantic_rank}")
        print(f"      - Execution mode: {hybrid_res.search_mode}")

        # -------------------------------------------------------------
        # 6. Repeated Same-Process Queries
        # -------------------------------------------------------------
        print("\n[6/6] Testing repeated same-process queries (no state corruption)...")
        queries = ["SQLite database", "FastAPI backend", "desktop search", "Python"]
        for q in queries:
            res = hybrid_engine.search(HybridSearchQuery(query=q, limit=2))
            assert res.keyword_available is True
            assert res.semantic_available is True
            assert res.search_mode in {"hybrid", "keyword_only", "semantic_only"}
            print(f"  ✓ Query '{q}' -> mode={res.search_mode}, {res.total_results} results in {res.execution_time_ms:.1f}ms")

    print("\n" + "=" * 70)
    print("ALL END-TO-END VERIFICATION CHECKS PASSED SUCCESSFULLY!")
    print("=" * 70)


if __name__ == "__main__":
    main()

