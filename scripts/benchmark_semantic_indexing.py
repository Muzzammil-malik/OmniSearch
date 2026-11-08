"""OmniSearch — Phase 10.5 Semantic Indexing Performance Benchmark.

Measures the exact baseline metrics for:
A. Cold model startup
B. Warm single embedding (text, image, audio, video)
C. Batch embedding vs single item embedding
D. Full indexing of representative corpus
E. Re-indexing of unchanged corpus
F. Partial modification indexing
G. Peak memory usage (RSS)
"""

import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import struct
import sys
import tempfile
import time
import wave
import numpy as np
from PIL import Image, ImageDraw

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from app.core.config import get_settings
from app.database.initialization import init_db
from app.database.repositories.files import FileRepository
from app.database.repositories.folders import FolderRepository
from app.embeddings.configuration import EmbeddingConfig
from app.embeddings.embedder import EmbeddingGemmaEmbedder
from app.embeddings.model_manager import EmbeddingModelManager
from app.services.indexer import IndexingService
from app.services.semantic_pipeline import SemanticPipeline
from app.vector_store.chroma import ChromaVectorStore


# ---------------------------------------------------------------------------
# Memory Measurement (Windows Native)
# ---------------------------------------------------------------------------

class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("PageFaultCount", wintypes.DWORD),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
    ]

GetProcessMemoryInfo = ctypes.windll.psapi.GetProcessMemoryInfo
GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESS_MEMORY_COUNTERS), wintypes.DWORD]
GetProcessMemoryInfo.restype = wintypes.BOOL


def get_peak_rss_mb() -> float:
    """Return peak working set memory usage in megabytes."""
    handle = ctypes.windll.kernel32.GetCurrentProcess()
    counters = PROCESS_MEMORY_COUNTERS()
    counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
    if GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
        return counters.PeakWorkingSetSize / (1024.0 * 1024.0)
    return 0.0


def get_current_rss_mb() -> float:
    """Return current working set memory usage in megabytes."""
    handle = ctypes.windll.kernel32.GetCurrentProcess()
    counters = PROCESS_MEMORY_COUNTERS()
    counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
    if GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
        return counters.WorkingSetSize / (1024.0 * 1024.0)
    return 0.0


# ---------------------------------------------------------------------------
# Test Corpus Helpers
# ---------------------------------------------------------------------------

def create_benchmark_corpus(target_dir: Path):
    """Generate representative multi-modal corpus for benchmarking."""
    target_dir.mkdir(parents=True, exist_ok=True)

    # 1. Multi-chunk text document (~600 words, ~4-5 chunks)
    doc_path = target_dir / "knowledge_base.txt"
    paragraphs = [
        "Distributed systems coordinate computing across networked nodes to achieve scalability and fault tolerance.",
        "Consensus algorithms like Raft and Paxos ensure state machine replication despite arbitrary network partitions.",
        "Vector databases utilize high-dimensional indexing algorithms such as Hierarchical Navigable Small World graphs.",
        "Relational database normalization optimizes transactional schemas into Third Normal Form to minimize redundancy.",
        "Hybrid search fuses dense semantic embeddings with lexical inverted indexes using reciprocal rank fusion.",
        "Local-first software stores all data on user-owned hardware and operates completely offline without cloud dependencies."
    ]
    doc_path.write_text("\n\n".join(paragraphs), encoding="utf-8")

    # 2. PDF Document (using PyMuPDF)
    import fitz
    pdf_path = target_dir / "architecture_spec.pdf"
    pdf_doc = fitz.open()
    page1 = pdf_doc.new_page()
    page1.insert_text((50, 72), "OmniSearch Technical Architecture Specification", fontsize=16)
    page1.insert_text((50, 100), "This document outlines the core components of the local search engine.", fontsize=11)
    page1.insert_text((50, 120), "Components include FastAPI backend, Next.js frontend, SQLite FTS5, and ChromaDB.", fontsize=11)
    page2 = pdf_doc.new_page()
    page2.insert_text((50, 72), "Chapter 2: Semantic Pipeline & Ingestion Queue", fontsize=14)
    page2.insert_text((50, 100), "Vectors are computed using EmbeddingGemma 2 with 768 dimensions.", fontsize=11)
    pdf_doc.save(str(pdf_path))
    pdf_doc.close()

    # 3. Image: Sunset scene
    img_path = target_dir / "sunset.jpg"
    img = Image.new("RGB", (640, 480), color=(240, 100, 30))
    draw = ImageDraw.Draw(img)
    draw.ellipse((260, 140, 380, 260), fill=(255, 230, 40))
    draw.rectangle((0, 300, 640, 480), fill=(10, 60, 160))
    img.save(img_path, quality=90)

    # 4. Audio: 440Hz tone WAV (1.5 seconds)
    audio_path = target_dir / "tone.wav"
    sr = 16000
    n_samples = int(1.5 * sr)
    with wave.open(str(audio_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        buf = bytearray()
        for i in range(n_samples):
            v = int(32767.0 * 0.4 * math.sin(2.0 * math.pi * 440.0 * i / sr))
            buf.extend(struct.pack("<h", v))
        wf.writeframes(buf)

    # 5. Video: Wave animation (6 frames)
    vid_path = target_dir / "waves.mp4"
    import av
    container = av.open(str(vid_path), mode="w")
    stream = container.add_stream("mpeg4", rate=10)
    stream.width = 128
    stream.height = 128
    stream.pix_fmt = "yuv420p"
    for i in range(6):
        arr = np.zeros((128, 128, 3), dtype=np.uint8)
        arr[:, :, 0] = np.clip(10 + i * 20, 0, 255)
        arr[:, :, 1] = np.clip(60 + i * 25, 0, 255)
        arr[:, :, 2] = np.clip(180 + i * 10, 0, 255)
        frame = av.VideoFrame.from_ndarray(arr, format="rgb24")
        for packet in stream.encode(frame):
            container.mux(packet)
    for packet in stream.encode():
        container.mux(packet)
    container.close()

    return {
        "text": doc_path,
        "pdf": pdf_path,
        "image": img_path,
        "audio": audio_path,
        "video": vid_path,
    }


# ---------------------------------------------------------------------------
# Benchmark Suite
# ---------------------------------------------------------------------------

def run_benchmark():
    print("=" * 70)
    print(" OmniSearch — Phase 10.5 Semantic Indexing Performance Benchmark")
    print("=" * 70)

    local_model_path = Path(os.path.expandvars(r"%LOCALAPPDATA%\OmniSearch\models\embeddinggemma-2"))
    if not local_model_path.exists():
        print(f"ERROR: Model path does not exist: {local_model_path}")
        sys.exit(1)

    results = {}

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_str:
        tmp_dir = Path(tmp_str)
        corpus_dir = tmp_dir / "corpus"
        files_dict = create_benchmark_corpus(corpus_dir)

        # -------------------------------------------------------------------
        # Benchmark A: Cold Model Startup & First Inference
        # -------------------------------------------------------------------
        print("\n[A] Measuring Cold Model Startup...")
        EmbeddingModelManager._instance = None  # Force clean instance
        t0 = time.perf_counter()
        config = EmbeddingConfig(
            model_id=str(local_model_path),
            dimension=768,
            device="cpu",
            precision="float32",
            local_files_only=True,
        )
        embedder = EmbeddingGemmaEmbedder(config=config)
        # First embedding triggers cold load
        q1 = embedder.embed_query("cold startup test query")
        t_cold = time.perf_counter() - t0
        results["cold_startup_sec"] = round(t_cold, 2)
        print(f"    Cold Startup & First Embedding: {t_cold:.2f}s | Peak RSS: {get_peak_rss_mb():.1f} MB")

        # -------------------------------------------------------------------
        # Benchmark B: Warm Single Embeddings per Modality
        # -------------------------------------------------------------------
        print("\n[B] Measuring Warm Single Embeddings (Model Resident)...")

        # 1. Warm text embedding
        t0 = time.perf_counter()
        q2 = embedder.embed_query("warm text query performance")
        t_warm_text = time.perf_counter() - t0
        results["warm_text_sec"] = round(t_warm_text, 4)
        print(f"    Warm Text Embedding:  {t_warm_text:.4f}s")

        # 2. Warm image embedding
        t0 = time.perf_counter()
        v_img = embedder.embed_image(str(files_dict["image"]))
        t_warm_img = time.perf_counter() - t0
        results["warm_image_sec"] = round(t_warm_img, 4)
        print(f"    Warm Image Embedding: {t_warm_img:.4f}s")

        # 3. Warm audio embedding
        t0 = time.perf_counter()
        v_audio = embedder.embed_audio(str(files_dict["audio"]))
        t_warm_audio = time.perf_counter() - t0
        results["warm_audio_sec"] = round(t_warm_audio, 4)
        print(f"    Warm Audio Embedding: {t_warm_audio:.4f}s")

        # 4. Warm video embedding
        t0 = time.perf_counter()
        v_vid = embedder.embed_video(str(files_dict["video"]))
        t_warm_vid = time.perf_counter() - t0
        results["warm_video_sec"] = round(t_warm_vid, 4)
        print(f"    Warm Video Embedding: {t_warm_vid:.4f}s")

        # -------------------------------------------------------------------
        # Benchmark C: Text Chunk Batching (1-by-1 vs Batched)
        # -------------------------------------------------------------------
        print("\n[C] Measuring Text Chunk Batching (8 chunks)...")
        test_chunks = [
            f"Chunk {i}: In computer science, algorithmic complexity describes execution bounds for problem size {i}."
            for i in range(8)
        ]

        # Single item repeated inference
        t0 = time.perf_counter()
        for chunk in test_chunks:
            _ = embedder.embed_documents([chunk])
        t_seq = time.perf_counter() - t0
        results["seq_8_chunks_sec"] = round(t_seq, 2)
        print(f"    Sequential (8 individual calls): {t_seq:.2f}s (avg: {t_seq/8:.3f}s/chunk)")

        # Batched inference
        t0 = time.perf_counter()
        _ = embedder.embed_documents(test_chunks)
        t_batch = time.perf_counter() - t0
        results["batch_8_chunks_sec"] = round(t_batch, 2)
        speedup = (t_seq / t_batch) if t_batch > 0 else 1.0
        print(f"    Batched (1 call with 8 chunks):  {t_batch:.2f}s (avg: {t_batch/8:.3f}s/chunk) -> {speedup:.2f}x speedup")

        # -------------------------------------------------------------------
        # Benchmark D: Full Corpus Initial Indexing
        # -------------------------------------------------------------------
        print("\n[D] Measuring Full Corpus Initial Indexing (5 files, text/pdf/img/audio/video)...")
        db_path = tmp_dir / "bench.db"
        vectors_path = tmp_dir / "bench_vectors"
        db = init_db(db_path)
        vector_store = ChromaVectorStore(persist_dir=vectors_path)
        pipeline = SemanticPipeline(db=db, embedder=embedder, vector_store=vector_store)
        indexer = IndexingService(db=db, semantic_pipeline=pipeline)

        with db.connection() as conn:
            f_rec = FolderRepository.get_or_create(conn, str(corpus_dir))
            f_id = f_rec.id

        t0 = time.perf_counter()
        job1 = indexer.index_folder(corpus_dir, generate_embeddings=True)
        t_initial_index = time.perf_counter() - t0
        results["initial_index_sec"] = round(t_initial_index, 2)
        v_count = vector_store.count()
        results["total_vectors_indexed"] = v_count
        print(f"    Initial Indexing: {t_initial_index:.2f}s | Files: {job1.successful_files} | Vectors: {v_count}")
        print(f"    Throughput: {job1.successful_files / t_initial_index:.2f} files/s | {v_count / t_initial_index:.2f} vectors/s")
        print(f"    Peak Memory: {get_peak_rss_mb():.1f} MB")

        # -------------------------------------------------------------------
        # Benchmark E: Re-indexing Unchanged Corpus
        # -------------------------------------------------------------------
        print("\n[E] Measuring Re-indexing Unchanged Corpus...")
        t0 = time.perf_counter()
        job2 = indexer.index_folder(corpus_dir, generate_embeddings=True)
        t_reindex = time.perf_counter() - t0
        results["reindex_unchanged_sec"] = round(t_reindex, 4)
        print(f"    Re-indexing Unchanged: {t_reindex:.4f}s | Skipped Files: {job2.skipped_files} | Vectors: {vector_store.count()}")

        # -------------------------------------------------------------------
        # Benchmark F: Single File Partial Modification
        # -------------------------------------------------------------------
        print("\n[F] Measuring Single File Partial Modification...")
        # Append 1 line to knowledge_base.txt
        with open(files_dict["text"], "a", encoding="utf-8") as f:
            f.write("\n\nAppend extra section on dynamic programming algorithms.")

        t0 = time.perf_counter()
        job3 = indexer.index_folder(corpus_dir, generate_embeddings=True)
        t_modified = time.perf_counter() - t0
        results["single_file_modified_sec"] = round(t_modified, 2)
        print(f"    Modified File Re-index: {t_modified:.2f}s | Processed: {job3.processed_files} | Skipped: {job3.skipped_files}")
        print(f"    Final Vector Count: {vector_store.count()} | Peak Memory: {get_peak_rss_mb():.1f} MB")

        results["peak_rss_mb"] = round(get_peak_rss_mb(), 1)

    print("\n" + "=" * 70)
    print(" BENCHMARK RESULTS SUMMARY (JSON)")
    print("=" * 70)
    print(json.dumps(results, indent=2))
    print("=" * 70)


if __name__ == "__main__":
    run_benchmark()

