"""OmniSearch Deep Vector Embedding Performance Diagnostic.

Diagnostic-only benchmark that measures:
1. Environment & Hardware Baseline (CPU, Cores, Threads, RAM, Versions, Config)
2. Model Warm-up (Model load time, First inference vs steady-state)
3. Controlled Model-Only Benchmarks:
   - Batch sizes: 8, 16, 32
   - Sequence lengths: 64, 128, 256, 384, 512 tokens
4. Full Real Pipeline Milestone Benchmarks (100, 250, 500, 1000, 2000 chunks) with detailed timing breakdown:
   - Input prep (SQLite retrieval, text extraction, prompt formatting)
   - Tokenization
   - Model inference
   - Pooling
   - MRL truncation
   - L2 Normalization
   - ChromaDB upsert
   - SQLite commit
5. Chunk Length Distribution & Token Statistics
6. Batch Behavior & Padded Length Analysis
7. CPU & RAM Utilization Telemetry
8. Duplicate-Work Audit
"""

import ctypes
from ctypes import wintypes
import gc
import json
import math
import os
from pathlib import Path
import statistics
import sys
import tempfile
import time
from typing import Any, Dict, List, Optional, Tuple

# Ensure backend is on sys.path
backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

# Detect/mask blocked scipy if needed
try:
    import scipy
except Exception:
    sys.modules["scipy"] = None

import torch
import transformers
import chromadb
from transformers import AutoModel, AutoTokenizer

from app.core.config import get_settings
from app.core.dependencies import TorchDependencyManager, ChromaDependencyManager
from app.database.connection import DatabaseConnectionManager
from app.database.migrations import apply_migrations
from app.database.repositories.chunks import ChunkRepository
from app.database.repositories.embeddings import ChunkEmbeddingRepository
from app.database.repositories.files import FileRepository
from app.database.repositories.folders import FolderRepository
from app.embeddings.configuration import EmbeddingConfig
from app.embeddings.embedder import EmbeddingGemmaEmbedder
from app.embeddings.model_manager import EmbeddingModelManager
from app.embeddings.prompts import format_document_prompt
from app.ingestion.extractors.text import TextExtractor
from app.processing.chunker import DocumentChunker
from app.schemas.processing import DocumentChunk, FileRecord
from app.services.semantic_pipeline import SemanticPipeline
from app.vector_store.chroma import ChromaVectorStore

# ---------------------------------------------------------------------------
# Windows Telemetry Utilities (ctypes)
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

class FILETIME(ctypes.Structure):
    _fields_ = [("dwLowDateTime", wintypes.DWORD), ("dwHighDateTime", wintypes.DWORD)]

kernel32 = ctypes.WinDLL("kernel32")
psapi = ctypes.WinDLL("psapi")

psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESS_MEMORY_COUNTERS), wintypes.DWORD]
psapi.GetProcessMemoryInfo.restype = wintypes.BOOL

kernel32.GetProcessTimes.argtypes = [
    wintypes.HANDLE,
    ctypes.POINTER(FILETIME),
    ctypes.POINTER(FILETIME),
    ctypes.POINTER(FILETIME),
    ctypes.POINTER(FILETIME),
]
kernel32.GetProcessTimes.restype = wintypes.BOOL

def get_process_rss_mb() -> float:
    try:
        counters = PROCESS_MEMORY_COUNTERS()
        counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
        handle = kernel32.GetCurrentProcess()
        if psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
            return counters.WorkingSetSize / (1024 * 1024)
    except Exception:
        pass
    return 0.0

def get_process_cpu_time() -> float:
    try:
        c, e, k, u = FILETIME(), FILETIME(), FILETIME(), FILETIME()
        handle = kernel32.GetCurrentProcess()
        if kernel32.GetProcessTimes(handle, ctypes.byref(c), ctypes.byref(e), ctypes.byref(k), ctypes.byref(u)):
            kt = (k.dwHighDateTime << 32) + k.dwLowDateTime
            ut = (u.dwHighDateTime << 32) + u.dwLowDateTime
            return (kt + ut) / 10_000_000.0
    except Exception:
        pass
    return 0.0


# ---------------------------------------------------------------------------
# Corpus Extraction & Realistic Chunk Generation
# ---------------------------------------------------------------------------
def collect_realistic_chunks(target_count: int = 2000) -> List[str]:
    """Collect real extracted chunks from workspace files, cycling if needed."""
    root = Path(__file__).resolve().parent.parent
    extractor = TextExtractor()
    chunker = DocumentChunker(target_tokens=500, overlap_tokens=80)
    
    unique_chunks: List[str] = []
    candidates = []
    for ext in ["*.md", "*.py", "*.ts", "*.tsx", "*.json", "*.txt"]:
        candidates.extend(root.rglob(ext))
        
    for p in sorted(candidates):
        if any(ign in p.parts for ign in {".venv", "node_modules", ".git", ".next", "__pycache__", ".test_data"}):
            continue
        try:
            doc = extractor.extract(p)
            doc_chunks = chunker.chunk_document(doc)
            for c in doc_chunks:
                text = c.content.strip()
                if len(text) > 40:
                    unique_chunks.append(text)
        except Exception:
            pass
            
    if not unique_chunks:
        raise RuntimeError("Failed to extract representative chunks from workspace.")
        
    # Cycle if fewer than target_count
    result: List[str] = []
    idx = 0
    while len(result) < target_count:
        result.append(unique_chunks[idx % len(unique_chunks)])
        idx += 1
    return result[:target_count]


# ---------------------------------------------------------------------------
# Benchmark Execution
# ---------------------------------------------------------------------------
def main():
    print("=" * 80)
    print("OMNISEARCH DEEP VECTOR EMBEDDING DIAGNOSTIC BENCHMARK")
    print("=" * 80)
    sys.stdout.flush()

    settings = get_settings()
    
    # 1. Baseline Environment Check
    print("\n--- 1. CURRENT BASELINE CONFIGURATION ---")
    print(f"Python Version: {sys.version.split()[0]}")
    print(f"PyTorch Version: {torch.__version__}")
    print(f"Transformers Version: {transformers.__version__}")
    print(f"ChromaDB Version: {chromadb.__version__}")
    print(f"Embedding Model ID: {settings.embedding_model_id}")
    print(f"Resolved Model Path: {settings.resolved_embedding_model}")
    print(f"Configured Dimension: {settings.embedding_dimension}")
    print(f"Configured Batch Size: {settings.embedding_batch_size}")
    print(f"Inference Device: {settings.embedding_device}")
    print(f"Inference Precision: {settings.embedding_precision}")
    print(f"PyTorch Intra-op Threads: {torch.get_num_threads()}")
    print(f"PyTorch Inter-op Threads: {torch.get_num_interop_threads()}")
    print(f"Process Baseline RSS: {get_process_rss_mb():.2f} MB")
    sys.stdout.flush()

    # 2. Model Warm-up & Initialization Measurement
    print("\n--- 2. MODEL WARM-UP & INITIALIZATION TIMING ---")
    manager = EmbeddingModelManager.get_instance()
    manager.unload()
    gc.collect()

    t_load_start = time.perf_counter()
    rss_before_load = get_process_rss_mb()
    config = EmbeddingConfig(
        model_id=settings.resolved_embedding_model,
        dimension=settings.embedding_dimension,
        batch_size=settings.embedding_batch_size,
        device=settings.embedding_device,
        precision=settings.embedding_precision,
    )
    tokenizer, model = manager.get_model_and_tokenizer(config)
    t_load_elapsed = time.perf_counter() - t_load_start
    rss_after_load = get_process_rss_mb()
    print(f"Model & Tokenizer Load Time: {t_load_elapsed:.4f} s")
    print(f"RAM increase during model load: {rss_after_load - rss_before_load:.2f} MB (Current RSS: {rss_after_load:.2f} MB)")
    sys.stdout.flush()

    # First inference test (cold forward pass)
    sample_text = ["OmniSearch architecture and system design for local-first desktop indexing."]
    prompt = [format_document_prompt(sample_text[0], "test.txt")]
    
    encoded_first = tokenizer(prompt, padding=True, truncation=True, max_length=512, return_tensors="pt")
    t_first_start = time.perf_counter()
    with torch.no_grad():
        out_first = model(**encoded_first)
        _ = out_first.last_hidden_state
    t_first_elapsed = time.perf_counter() - t_first_start
    print(f"Cold First-Batch Inference Time (1 sample): {t_first_elapsed:.4f} s")

    # Second inference test (steady-state forward pass)
    t_steady_start = time.perf_counter()
    with torch.no_grad():
        out_steady = model(**encoded_first)
        _ = out_steady.last_hidden_state
    t_steady_elapsed = time.perf_counter() - t_steady_start
    print(f"Warm Second-Batch Inference Time (1 sample): {t_steady_elapsed:.4f} s")
    sys.stdout.flush()

    # 3. Controlled Model-Only Benchmarks
    print("\n--- 3. CONTROLLED MODEL-ONLY BENCHMARK: BATCH SIZE SCALING ---")
    corpus_all = collect_realistic_chunks(2000)
    print(f"Extracted {len(corpus_all)} realistic chunks from workspace files.")

    # Measure batch sizes 8, 16, 32 with representative chunks (32 chunks each)
    batch_test_samples = corpus_all[:32]
    prompts_32 = [format_document_prompt(t, f"doc_{i}.txt") for i, t in enumerate(batch_test_samples)]

    for bs in [8, 16, 32]:
        encoded = tokenizer(prompts_32, padding=True, truncation=True, max_length=512, return_tensors="pt")
        # Run in slices of bs
        total_time = 0.0
        num_batches = len(prompts_32) // bs
        rss_start = get_process_rss_mb()
        cpu_time_start = get_process_cpu_time()
        wall_start = time.perf_counter()

        with torch.no_grad():
            for i in range(0, len(prompts_32), bs):
                sub_inputs = {k: v[i : i + bs] for k, v in encoded.items()}
                t0 = time.perf_counter()
                out = model(**sub_inputs)
                _ = out.last_hidden_state
                total_time += (time.perf_counter() - t0)

        wall_elapsed = time.perf_counter() - wall_start
        cpu_elapsed = get_process_cpu_time() - cpu_time_start
        rss_peak = get_process_rss_mb()
        cpu_pct = (cpu_elapsed / wall_elapsed * 100.0) if wall_elapsed > 0 else 0.0

        throughput = len(prompts_32) / total_time
        sec_per_batch = total_time / num_batches
        print(f"Batch Size {bs:2d} -> Model Forward Time: {total_time:.3f} s | Throughput: {throughput:.2f} emb/s | {sec_per_batch:.3f} s/batch | Peak RSS: {rss_peak:.1f} MB | CPU Util: {cpu_pct:.1f}%")
        sys.stdout.flush()

    # 4. Controlled Model-Only Benchmark: Sequence Length Scaling
    print("\n--- 4. CONTROLLED MODEL-ONLY BENCHMARK: SEQUENCE LENGTH SCALING ---")
    # Test 16 samples padded to fixed sequence lengths: 64, 128, 256, 384, 512
    fixed_bs = 16
    for seq_len in [64, 128, 256, 384, 512]:
        # Synthesize exactly seq_len tokens
        dummy_ids = torch.randint(100, 3000, (fixed_bs, seq_len), dtype=torch.long)
        dummy_mask = torch.ones((fixed_bs, seq_len), dtype=torch.long)
        inputs = {"input_ids": dummy_ids, "attention_mask": dummy_mask}

        cpu_time_start = get_process_cpu_time()
        wall_start = time.perf_counter()
        with torch.no_grad():
            out = model(**inputs)
            _ = out.last_hidden_state
        wall_elapsed = time.perf_counter() - wall_start
        cpu_elapsed = get_process_cpu_time() - cpu_time_start
        cpu_pct = (cpu_elapsed / wall_elapsed * 100.0) if wall_elapsed > 0 else 0.0
        throughput = fixed_bs / wall_elapsed

        print(f"Sequence Length {seq_len:3d} tokens -> Forward Time: {wall_elapsed:.3f} s | Throughput: {throughput:.2f} emb/s | CPU Util: {cpu_pct:.1f}%")
        sys.stdout.flush()

    # 5. Real Pipeline Milestone Benchmarks (100, 250, 500, 1000, 2000 chunks)
    print("\n--- 5. FULL REAL PIPELINE BENCHMARKS (100 -> 2000 CHUNKS) ---")
    print("Executing complete production pipeline (SQLite -> Tokenizer -> Model -> Pooling -> MRL -> Norm -> ChromaDB -> SQLite Commit)...")
    sys.stdout.flush()

    # Analyze chunk length distribution across the 2,000 chunks
    print("\nComputing chunk length distribution across corpus...")
    token_lengths = [len(tokenizer.encode(t, truncation=False)) for t in corpus_all]
    token_lengths_sorted = sorted(token_lengths)
    n_chunks = len(token_lengths)
    
    min_len = token_lengths_sorted[0]
    p25_len = token_lengths_sorted[int(n_chunks * 0.25)]
    med_len = token_lengths_sorted[int(n_chunks * 0.50)]
    p75_len = token_lengths_sorted[int(n_chunks * 0.75)]
    p90_len = token_lengths_sorted[int(n_chunks * 0.90)]
    p95_len = token_lengths_sorted[int(n_chunks * 0.95)]
    p99_len = token_lengths_sorted[int(n_chunks * 0.99)]
    max_len = token_lengths_sorted[-1]
    avg_len = sum(token_lengths) / n_chunks

    print(f"Token Lengths: Min={min_len}, P25={p25_len}, Median={med_len}, P75={p75_len}, P90={p90_len}, P95={p95_len}, P99={p99_len}, Max={max_len}, Avg={avg_len:.1f}")

    # Buckets: 0-64, 65-128, 129-256, 257-384, 385-512, >512
    b_64 = sum(1 for l in token_lengths if l <= 64)
    b_128 = sum(1 for l in token_lengths if 65 <= l <= 128)
    b_256 = sum(1 for l in token_lengths if 129 <= l <= 256)
    b_384 = sum(1 for l in token_lengths if 257 <= l <= 384)
    b_512 = sum(1 for l in token_lengths if 385 <= l <= 512)
    b_gt512 = sum(1 for l in token_lengths if l > 512)

    print("Bucket Distribution:")
    print(f"  0-64 tokens:   {b_64:4d} ({b_64 / n_chunks * 100:.1f}%)")
    print(f"  65-128 tokens: {b_128:4d} ({b_128 / n_chunks * 100:.1f}%)")
    print(f"  129-256 tokens:{b_256:4d} ({b_256 / n_chunks * 100:.1f}%)")
    print(f"  257-384 tokens:{b_384:4d} ({b_384 / n_chunks * 100:.1f}%)")
    print(f"  385-512 tokens:{b_512:4d} ({b_512 / n_chunks * 100:.1f}%)")
    print(f"  >512 tokens:   {b_gt512:4d} ({b_gt512 / n_chunks * 100:.1f}%)")
    sys.stdout.flush()

    # Run the instrumented real pipeline milestone run
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir_str:
        tmp_dir = Path(tmp_dir_str)
        db_path = tmp_dir / "profile_test.db"
        vectors_dir = tmp_dir / "vectors"
        vectors_dir.mkdir(parents=True, exist_ok=True)

        db = DatabaseConnectionManager(db_path=db_path)
        with db.connection() as conn:
            apply_migrations(conn)

        vector_store = ChromaVectorStore(persist_dir=str(vectors_dir), collection_name="profile_bench")
        embedder = EmbeddingGemmaEmbedder(config=config, model_manager=manager)

        # Populate SQLite with 2,000 document chunks
        print("\nPopulating test SQLite database with 2,000 DocumentChunks...")
        with db.transaction() as conn:
            folder = FolderRepository.get_or_create(conn, str(tmp_dir / "docs"))
            from datetime import datetime, timezone
            file_rec = FileRecord(
                folder_id=folder.id,
                path=str(tmp_dir / "docs" / "representative_corpus.md"),
                filename="representative_corpus.md",
                extension=".md",
                file_type="document",
                size_bytes=500000,
                modified_at=datetime.now(timezone.utc).isoformat(),
                status="success",
            )
            file_id = FileRepository.upsert(conn, file_rec)

            doc_chunks = []
            for i, text in enumerate(corpus_all):
                doc_chunks.append(DocumentChunk(
                    file_id=file_id,
                    chunk_index=i,
                    content=text,
                    char_count=len(text),
                    token_count=token_lengths[i],
                    page_number=1 + (i // 10),
                ))
            ChunkRepository.insert_chunks(conn, file_id, doc_chunks)

        with db.connection() as conn:
            unembedded_initial = ChunkEmbeddingRepository.count_unembedded(conn)
        print(f"Confirmed unembedded chunks in DB: {unembedded_initial}")
        sys.stdout.flush()

        # Instrumentation accumulators
        timings = {
            "sqlite_read": 0.0,
            "tokenization": 0.0,
            "model_inference": 0.0,
            "pooling": 0.0,
            "mrl": 0.0,
            "normalization": 0.0,
            "chroma_upsert": 0.0,
            "sqlite_commit": 0.0,
            "wall_clock": 0.0,
        }

        # Milestone reporting targets
        milestones = [100, 250, 500, 1000, 2000]
        milestone_data = {}

        batch_size = 16
        total_processed = 0
        batch_padded_lengths = []
        batch_actual_max_lengths = []
        batch_sizes = []

        pipeline_start_wall = time.perf_counter()
        pipeline_start_cpu = get_process_cpu_time()

        while total_processed < 2000:
            limit = min(batch_size, 2000 - total_processed)

            # Stage A: SQLite Read
            t0 = time.perf_counter()
            with db.connection() as conn:
                unembedded_rows = ChunkEmbeddingRepository.get_unembedded_chunks(conn, limit=limit)
            if not unembedded_rows:
                break
            timings["sqlite_read"] += (time.perf_counter() - t0)

            chunk_ids = [r["chunk_id"] for r in unembedded_rows]
            file_ids = [r["file_id"] for r in unembedded_rows]
            contents = [r["content"] for r in unembedded_rows]
            titles = [r["filename"] for r in unembedded_rows]
            metadatas = [
                {
                    "file_id": r["file_id"],
                    "filename": r["filename"],
                    "file_type": r["file_type"],
                    "content_type": "document",
                    "folder_id": r["folder_id"],
                    "chunk_index": r["chunk_index"],
                    "page_number": r["page_number"],
                    "slide_number": r["slide_number"],
                    "sheet_name": r["sheet_name"],
                    "start_line": r["start_line"],
                    "end_line": r["end_line"],
                    "path": r["file_path"],
                    "embedding_source": "text",
                }
                for r in unembedded_rows
            ]

            # Stage B: Prompt Formatting & Tokenization
            t0 = time.perf_counter()
            prompts = [format_document_prompt(c, t) for c, t in zip(contents, titles)]
            encoded = tokenizer(prompts, padding=True, truncation=True, max_length=512, return_tensors="pt")
            timings["tokenization"] += (time.perf_counter() - t0)

            # Record batch behavior
            actual_lens = [int(mask.sum()) for mask in encoded["attention_mask"]]
            padded_len = int(encoded["input_ids"].shape[1])
            batch_padded_lengths.append(padded_len)
            batch_actual_max_lengths.append(max(actual_lens))
            batch_sizes.append(len(prompts))

            # Stage C: Model Inference
            t0 = time.perf_counter()
            with torch.no_grad():
                outputs = model(**encoded)
                last_hidden = outputs.last_hidden_state
            timings["model_inference"] += (time.perf_counter() - t0)

            # Stage D: Attention-Weighted Mean Pooling
            t0 = time.perf_counter()
            attention_mask = encoded["attention_mask"].unsqueeze(-1)
            sum_embeddings = torch.sum(last_hidden * attention_mask, dim=1)
            sum_mask = torch.clamp(attention_mask.sum(dim=1), min=1e-9)
            pooled = sum_embeddings / sum_mask
            timings["pooling"] += (time.perf_counter() - t0)

            # Stage E: MRL Truncation
            t0 = time.perf_counter()
            if config.dimension < pooled.shape[-1]:
                pooled = pooled[:, : config.dimension]
            timings["mrl"] += (time.perf_counter() - t0)

            # Stage F: L2 Normalization & tolist
            t0 = time.perf_counter()
            normalized = torch.nn.functional.normalize(pooled, p=2, dim=1)
            batch_embeddings = normalized.cpu().tolist()
            timings["normalization"] += (time.perf_counter() - t0)

            # Stage G: ChromaDB Upsert
            t0 = time.perf_counter()
            vector_store.upsert(
                chunk_ids=chunk_ids,
                embeddings=batch_embeddings,
                metadatas=metadatas,
                documents=contents,
            )
            timings["chroma_upsert"] += (time.perf_counter() - t0)

            # Stage H: SQLite Commit
            t0 = time.perf_counter()
            records_to_commit = [
                (cid, fid, config.model_id, config.dimension)
                for cid, fid in zip(chunk_ids, file_ids)
            ]
            with db.transaction() as conn:
                ChunkEmbeddingRepository.record_batch(conn, records_to_commit)
            timings["sqlite_commit"] += (time.perf_counter() - t0)

            total_processed += len(chunk_ids)

            # Check if milestone reached
            for m in milestones:
                if total_processed >= m and m not in milestone_data:
                    elapsed_so_far = time.perf_counter() - pipeline_start_wall
                    cpu_so_far = get_process_cpu_time() - pipeline_start_cpu
                    milestone_data[m] = {
                        "chunks": m,
                        "wall_time": elapsed_so_far,
                        "throughput": m / elapsed_so_far,
                        "cpu_util_pct": (cpu_so_far / elapsed_so_far * 100.0) if elapsed_so_far > 0 else 0.0,
                        "snapshot_timings": dict(timings),
                        "rss_mb": get_process_rss_mb(),
                    }
                    print(f"Milestone {m:4d} chunks completed in {elapsed_so_far:.2f} s ({m / elapsed_so_far:.2f} emb/s) | RSS: {get_process_rss_mb():.1f} MB")
                    sys.stdout.flush()

        timings["wall_clock"] = time.perf_counter() - pipeline_start_wall
        total_cpu_elapsed = get_process_cpu_time() - pipeline_start_cpu
        avg_cpu_pct = (total_cpu_elapsed / timings["wall_clock"] * 100.0) if timings["wall_clock"] > 0 else 0.0

        print(f"\nCompleted 2,000 chunks in {timings['wall_clock']:.2f} seconds ({2000 / timings['wall_clock']:.2f} emb/s).")
        print(f"Average CPU utilization across entire pipeline: {avg_cpu_pct:.1f}%")
        sys.stdout.flush()

        # Print Milestone Summary Table
        print("\n" + "=" * 80)
        print("MILESTONE SUMMARY RESULTS")
        print("=" * 80)
        print(f"{'Chunks':>8} | {'Wall Time (s)':>14} | {'Throughput (emb/s)':>20} | {'CPU Util (%)':>14} | {'Process RSS (MB)':>18}")
        print("-" * 80)
        for m in milestones:
            d = milestone_data[m]
            print(f"{d['chunks']:8d} | {d['wall_time']:14.2f} | {d['throughput']:20.2f} | {d['cpu_util_pct']:14.1f} | {d['rss_mb']:18.1f}")
        sys.stdout.flush()

        # Print Detailed Timing Breakdown Table (for 2,000 chunks)
        print("\n" + "=" * 80)
        print("DETAILED PIPELINE STAGE BREAKDOWN (2,000 CHUNKS)")
        print("=" * 80)
        total_wall = timings["wall_clock"]
        sum_measured = (
            timings["sqlite_read"]
            + timings["tokenization"]
            + timings["model_inference"]
            + timings["pooling"]
            + timings["mrl"]
            + timings["normalization"]
            + timings["chroma_upsert"]
            + timings["sqlite_commit"]
        )
        other_time = max(0.0, total_wall - sum_measured)

        stage_rows = [
            ("SQLite read (get unembedded)", timings["sqlite_read"]),
            ("Tokenization & prompt format", timings["tokenization"]),
            ("Model forward inference", timings["model_inference"]),
            ("Mean pooling", timings["pooling"]),
            ("MRL truncation", timings["mrl"]),
            ("L2 normalization & tolist", timings["normalization"]),
            ("ChromaDB upsert", timings["chroma_upsert"]),
            ("SQLite commit (record_batch)", timings["sqlite_commit"]),
            ("Other (Python loops/overhead)", other_time),
        ]

        print(f"{'Pipeline Stage':<35} | {'Time (s)':>12} | {'% of Total':>12}")
        print("-" * 65)
        for name, duration in stage_rows:
            pct = (duration / total_wall * 100.0) if total_wall > 0 else 0.0
            print(f"{name:<35} | {duration:12.3f} | {pct:11.2f}%")
        print("-" * 65)
        print(f"{'TOTAL PIPELINE WALL CLOCK':<35} | {total_wall:12.3f} | {'100.00%':>12}")
        sys.stdout.flush()

        # Batch behavior details
        print("\n" + "=" * 80)
        print("BATCH BEHAVIOR & PADDING ANALYSIS")
        print("=" * 80)
        print(f"Total Chunks Processed: {total_processed}")
        print(f"Total Batches Executed: {len(batch_sizes)}")
        print(f"Average Batch Size: {sum(batch_sizes) / len(batch_sizes):.2f}")
        print(f"Min Batch Size: {min(batch_sizes)}, Max Batch Size: {max(batch_sizes)}")
        print(f"Average Actual Max Tokens per Batch: {sum(batch_actual_max_lengths) / len(batch_actual_max_lengths):.1f}")
        print(f"Average Padded Tokens per Batch: {sum(batch_padded_lengths) / len(batch_padded_lengths):.1f}")
        print(f"Dynamic Longest Padding Ratio: {(sum(batch_padded_lengths) / len(batch_padded_lengths)) / 512.0 * 100.0:.1f}% of fixed 512 max length")
        sys.stdout.flush()

        # 6. Duplicate-Work Audit
        print("\n" + "=" * 80)
        print("DUPLICATE-WORK & REDUNDANCY AUDIT")
        print("=" * 80)
        with db.connection() as conn:
            final_unembedded = ChunkEmbeddingRepository.count_unembedded(conn)
            cursor = conn.cursor()
            cursor.execute("SELECT chunk_id, COUNT(*) FROM chunk_embeddings GROUP BY chunk_id HAVING COUNT(*) > 1")
            duplicate_embeddings = cursor.fetchall()
            cursor.close()

        print(f"Remaining unembedded chunks in DB: {final_unembedded} (Expected: 0)")
        print(f"Duplicate chunk_embeddings records in SQLite: {len(duplicate_embeddings)} (Expected: 0)")
        print(f"ChromaDB total vectors in collection: {vector_store.count()} (Expected: 2000)")

        # Verify idempotency: sync_embeddings on already-embedded collection
        t_idempotent_start = time.perf_counter()
        pipeline = SemanticPipeline(db=db, embedder=embedder, vector_store=vector_store, batch_size=16)
        second_sync_count = pipeline.sync_embeddings()
        t_idempotent_elapsed = time.perf_counter() - t_idempotent_start
        print(f"Second sync_embeddings() run result: {second_sync_count} chunks embedded in {t_idempotent_elapsed:.4f} s (Expected: 0 chunks, <0.01 s)")

    print("\n" + "=" * 80)
    print("BENCHMARK AND DIAGNOSTIC SUITE COMPLETE")
    print("=" * 80)
    sys.stdout.flush()

if __name__ == "__main__":
    main()

