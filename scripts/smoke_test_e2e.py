"""OmniSearch Phase 10.5B — End-to-End Verification Smoke Test Suite.

Executes and verifies:
1. Index a small folder.
2. Generate semantic embeddings.
3. Perform keyword search.
4. Perform semantic search.
5. Verify result IDs.
6. Verify embeddings are persisted in ChromaDB and SQLite.
7. Verify re-running indexing does not duplicate embeddings.
8. Verify incremental indexing.
9. Verify a modified file receives updated embeddings.
10. Verify deleted content is handled correctly.
"""

from datetime import datetime, timezone
import os
from pathlib import Path
import sys
import tempfile
import time

backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from app.core.dependencies import TorchDependencyManager, ScipyDependencyManager
from app.database.connection import DatabaseConnectionManager
from app.database.migrations import apply_migrations
from app.database.repositories.chunks import ChunkRepository
from app.database.repositories.embeddings import ChunkEmbeddingRepository
from app.database.repositories.files import FileRepository
from app.database.repositories.folders import FolderRepository
from app.embeddings.configuration import EmbeddingConfig
from app.embeddings.embedder import EmbeddingGemmaEmbedder
from app.schemas.search import SearchQuery
from app.search.keyword_search import KeywordSearchEngine
from app.search.semantic_search import SemanticSearchEngine
from app.services.indexer import IndexingService
from app.services.semantic_pipeline import SemanticPipeline
from app.vector_store.chroma import ChromaVectorStore


def run_smoke_tests():
    print("=================================================================")
    print("OmniSearch Phase 10.5B End-to-End Verification Smoke Tests")
    print("=================================================================")

    # Initialize PyTorch and Scipy manager
    torch_mgr = TorchDependencyManager.get_instance()
    torch_mgr.ensure_torch()
    scipy_mgr = ScipyDependencyManager.get_instance()
    scipy_mgr.check_capability()

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir_str:
        tmp_dir = Path(tmp_dir_str)
        test_folder = tmp_dir / "test_docs"
        test_folder.mkdir(parents=True, exist_ok=True)
        db_path = tmp_dir / "smoke.db"
        vectors_dir = tmp_dir / "vectors"
        vectors_dir.mkdir(parents=True, exist_ok=True)

        db = DatabaseConnectionManager(db_path=db_path)
        with db.connection() as conn:
            apply_migrations(conn)

        config = EmbeddingConfig(dimension=768, batch_size=16, num_threads=6)
        embedder = EmbeddingGemmaEmbedder(config=config)
        vector_store = ChromaVectorStore(persist_dir=str(vectors_dir))
        pipeline = SemanticPipeline(db=db, embedder=embedder, vector_store=vector_store, batch_size=16)
        indexer = IndexingService(db=db, semantic_pipeline=pipeline)

        # 1. Index a small folder
        print("\n[Step 1] Creating files and indexing small folder...")
        file1 = test_folder / "quantum_computing.txt"
        file1.write_text("Quantum computers use qubits to perform superposition and entanglement calculations.", encoding="utf-8")

        file2 = test_folder / "machine_learning.txt"
        file2.write_text("Deep neural networks and transformers optimize weights using gradient descent backpropagation.", encoding="utf-8")

        file3 = test_folder / "database_systems.txt"
        file3.write_text("Relational databases use B-tree indexes and write-ahead logging to guarantee ACID transactions.", encoding="utf-8")

        job_record = indexer.index_folder(test_folder, generate_embeddings=True)
        assert job_record.processed_files == 3, f"Expected 3 processed files, got {job_record.processed_files}"
        print(f"-> Successfully indexed {job_record.processed_files} files (Job ID: {job_record.id})")

        # 2. Generate semantic embeddings
        print("\n[Step 2] Verifying semantic embeddings...")
        with db.connection() as conn:
            unembedded = ChunkEmbeddingRepository.count_unembedded(conn)
            assert unembedded == 0, f"Expected 0 unembedded chunks, got {unembedded}"
            embedded_count = ChunkEmbeddingRepository.count_embedded(conn)
            assert embedded_count == 3, f"Expected 3 embedded chunks, got {embedded_count}"
        assert vector_store.count() == 3, f"Expected 3 vectors in ChromaDB, got {vector_store.count()}"
        print(f"-> Verified 3 embeddings generated and stored in ChromaDB")

        # 3. Perform keyword search
        print("\n[Step 3] Performing keyword search...")
        kw_engine = KeywordSearchEngine(db=db)
        kw_res = kw_engine.search(SearchQuery(query="qubits superposition"))
        assert kw_res.total_results >= 1, "Keyword search for 'qubits superposition' returned 0 results"
        print(f"-> Keyword search returned {kw_res.total_results} result(s): {kw_res.results[0].filename}")

        # 4. Perform semantic search
        print("\n[Step 4] Performing semantic search...")
        sem_engine = SemanticSearchEngine(db=db, embedder=embedder, vector_store=vector_store)
        sem_res = sem_engine.search("artificial intelligence algorithms")
        assert sem_res.total_results >= 1, "Semantic search returned 0 results"
        top_match = sem_res.results[0]
        print(f"-> Top semantic match for 'artificial intelligence algorithms': {top_match.filename} (score: {top_match.score:.3f})")
        assert "machine_learning" in top_match.filename.lower()

        # 5. Verify result IDs
        print("\n[Step 5] Verifying result IDs and provenance consistency...")
        with db.connection() as conn:
            chunks = ChunkRepository.get_by_file_id(conn, top_match.file_id)
            matching_chunks = [c for c in chunks if c.id == top_match.chunk_id]
            assert len(matching_chunks) == 1, f"Chunk {top_match.chunk_id} not found in file {top_match.file_id}"
            chunk_rec = matching_chunks[0]
            print(f"-> Verified chunk {top_match.chunk_id} maps to file {top_match.file_id} ('{chunk_rec.content[:40]}...')")

        # 6. Verify embeddings are persisted
        print("\n[Step 6] Verifying persistence integrity...")
        with db.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM chunk_embeddings WHERE chunk_id = ?;", (top_match.chunk_id,))
            prov_row = cursor.fetchone()
            assert prov_row is not None, "Provenance record missing in SQLite chunk_embeddings"
            cursor.close()
        print("-> Verified embedding provenance record confirmed in SQLite")

        # 7. Verify re-running indexing does not duplicate embeddings
        print("\n[Step 7] Re-running indexing without file changes...")
        job_record2 = indexer.index_folder(test_folder, generate_embeddings=True)
        assert job_record2.skipped_files == 3, f"Expected 3 skipped files, got {job_record2.skipped_files}"
        with db.connection() as conn:
            total_chunks = ChunkRepository.count_total(conn)
            total_embeddings = ChunkEmbeddingRepository.count_embedded(conn)
            assert total_chunks == 3, f"Duplicate chunks created: {total_chunks}"
            assert total_embeddings == 3, f"Duplicate embeddings created: {total_embeddings}"
        assert vector_store.count() == 3, f"Vector count drifted: {vector_store.count()}"
        print(f"-> Confirmed 0 duplicate chunks or embeddings created (count remains 3)")

        # 8. Verify incremental indexing (adding a new file)
        print("\n[Step 8] Incremental indexing with new file...")
        file4 = test_folder / "astronomy.txt"
        file4.write_text("Exoplanets orbiting distant stars are detected via transit photometry and radial velocity.", encoding="utf-8")

        indexer.index_single_file(file4, generate_embeddings=True)
        with db.connection() as conn:
            assert ChunkRepository.count_total(conn) == 4
            assert ChunkEmbeddingRepository.count_embedded(conn) == 4
        assert vector_store.count() == 4
        print("-> Incremental file successfully indexed, embedded, and added to vector store (count = 4)")

        # 9. Verify modified file receives updated embeddings
        print("\n[Step 9] Modifying an existing file...")
        file1.write_text("Quantum computers use superconducting transmon qubits and trapped ions for quantum supremacy.", encoding="utf-8")
        indexer.index_single_file(file1, generate_embeddings=True)
        with db.connection() as conn:
            assert ChunkRepository.count_total(conn) == 4
            assert ChunkEmbeddingRepository.count_embedded(conn) == 4
        assert vector_store.count() == 4

        # Search for newly updated content
        kw_res_updated = kw_engine.search(SearchQuery(query="superconducting transmon"))
        assert kw_res_updated.total_results >= 1, "Updated keyword search failed"
        print("-> Modified file correctly re-indexed with updated chunks and embeddings (count = 4)")

        # 10. Verify deleted content is handled correctly
        print("\n[Step 10] Deleting a file...")
        indexer.delete_single_file(file4)
        if file4.exists():
            file4.unlink()

        with db.connection() as conn:
            assert ChunkRepository.count_total(conn) == 3
            assert ChunkEmbeddingRepository.count_embedded(conn) == 3
        assert vector_store.count() == 3
        print("-> Deleted file removed cleanly from SQLite chunks, provenance, and ChromaDB (count = 3)")

        print("\n=================================================================")
        print("ALL 10 VERIFICATION SMOKE TESTS PASSED CLEANLY!")
        print("=================================================================")


if __name__ == "__main__":
    run_smoke_tests()
