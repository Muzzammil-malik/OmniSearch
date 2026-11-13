"""Comprehensive benchmark evaluating the optimized OmniSearch embedding pipeline on up to 2,000 chunks."""

import os
import sys
import tempfile
import time
from pathlib import Path

# Add backend directory
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
from app.schemas.processing import DocumentChunk, FileRecord
from app.services.semantic_pipeline import SemanticPipeline
from app.vector_store.chroma import ChromaVectorStore


CORPUS_PARAGRAPHS = [
    "OmniSearch local-first desktop multifile search application architecture and system design.",
    "FastAPI provides the high performance asynchronous web API for desktop and local clients with high concurrency.",
    "SQLite with FTS5 enables authoritative full-text indexing, BM25 scoring, and metadata persistence without server dependencies.",
    "ChromaDB delivers persistent vector embeddings storage and fast nearest neighbor cosine similarity search across multi-thousand chunk collections.",
    "EmbeddingGemma 2 produces 768-dimensional multimodal vector representations on local CPU inference with Matryoshka representation learning.",
    "SentenceTransformers integration provides unified embeddings for documents, images, audio, and video formats natively.",
    "File watchers track file creation, modification, and deletion events using watchdog on Windows with debounce coalescing windows.",
    "Startup reconciliation scans registered folders and reconciles filesystem state against SQLite records using fast stat diffing.",
    "Hybrid search fuses SQLite BM25 keyword rankings with ChromaDB semantic vector cosine rankings via Reciprocal Rank Fusion.",
    "Reciprocal Rank Fusion with smoothing constant k=60 computes combined rank positions across candidate pools deterministically.",
    "PyMuPDF extracts text, layout structures, and embedded images from PDF documents quickly and reliably across all document standards.",
    "Local OCR processing using Tesseract extracts text from image-only scanned PDFs without cloud dependencies or telemetry.",
]


def run_benchmark(num_chunks: int = 500):
    print(f"\n=================================================================")
    print(f"Running Optimized Pipeline Benchmark on {num_chunks} chunks")
    print(f"=================================================================")

    # Initialize PyTorch and check capabilities
    torch_mgr = TorchDependencyManager.get_instance()
    torch = torch_mgr.ensure_torch()
    scipy_mgr = ScipyDependencyManager.get_instance()
    scipy_mgr.check_capability()

    print(f"PyTorch threads: {torch.get_num_threads()}")
    print(f"SciPy available: {scipy_mgr.is_available()} (Blocked: {scipy_mgr.is_blocked()})")

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir_str:
        tmp_dir = Path(tmp_dir_str)
        db_path = tmp_dir / "bench.db"
        vectors_dir = tmp_dir / "vectors"
        vectors_dir.mkdir(parents=True, exist_ok=True)

        db = DatabaseConnectionManager(db_path=db_path)
        with db.connection() as conn:
            apply_migrations(conn)

        config = EmbeddingConfig(dimension=768, batch_size=16, num_threads=6)
        embedder = EmbeddingGemmaEmbedder(config=config)
        vector_store = ChromaVectorStore(persist_dir=str(vectors_dir))
        pipeline = SemanticPipeline(db=db, embedder=embedder, vector_store=vector_store, batch_size=16)

        # Prepare corpus with varying lengths (50 to 350 words)
        print("Populating SQLite with test chunks...")
        with db.transaction() as conn:
            folder = FolderRepository.get_or_create(conn, str(tmp_dir))
            folder_id = folder.id
            from datetime import datetime, timezone
            file_rec = FileRecord(
                folder_id=folder_id,
                path=str(tmp_dir / "corpus.txt"),
                filename="corpus.txt",
                extension=".txt",
                file_type="document",
                size_bytes=100000,
                modified_at=datetime.now(timezone.utc).isoformat(),
                status="success",
            )
            file_id = FileRepository.upsert(conn, file_rec)

            chunks = []
            para_len = len(CORPUS_PARAGRAPHS)
            for i in range(num_chunks):
                # Mix varying paragraph counts to simulate real chunk distribution
                p_count = 1 + (i % 4)
                text = " ".join(CORPUS_PARAGRAPHS[(i + j) % para_len] for j in range(p_count))
                w_count = len(text.split())
                chunks.append(DocumentChunk(
                    file_id=file_id,
                    chunk_index=i,
                    content=text,
                    char_count=len(text),
                    word_count=w_count,
                    token_count=int(w_count * 1.3),
                ))
            ChunkRepository.insert_chunks(conn, file_id, chunks)

        print(f"Populated {num_chunks} chunks. Executing semantic pipeline sync...")

        t_start = time.perf_counter()
        embedded_count = pipeline.sync_embeddings()
        total_time = time.perf_counter() - t_start

        throughput = embedded_count / total_time if total_time > 0 else 0
        print(f"\n--- BENCHMARK RESULTS ({embedded_count} chunks) ---")
        print(f"Total Pipeline Time: {total_time:.3f} s")
        print(f"Throughput: {throughput:.2f} embeddings/sec")
        print(f"Average time per chunk: {(total_time / embedded_count) * 1000:.2f} ms")
        print(f"ChromaDB collection count: {vector_store.count()}")

        with db.connection() as conn:
            prov_count = ChunkEmbeddingRepository.count_embedded(conn)
            print(f"SQLite chunk_embeddings count: {prov_count}")

        return {
            "num_chunks": embedded_count,
            "total_time": total_time,
            "throughput": throughput,
        }


if __name__ == "__main__":
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 500
    run_benchmark(count)
