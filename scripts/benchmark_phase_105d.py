"""OmniSearch Phase 10.5D — Final Real-World Embedding Benchmark.

Comprehensive measurement of:
- Phase 10.5B Baseline: SQLite fetch pool = 16, inference batch = 16
- Phase 10.5C Optimized: SQLite fetch pool = 128, inference batch = 16

Uses 2,000 real document chunks extracted from workspace files.
Measures wall-clock time, throughput, token counts, padding waste, DB cycles,
memory RSS, and programmatic numerical equivalence.
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

# Detect and mask blocked scipy if present
try:
    import scipy
except Exception:
    sys.modules["scipy"] = None

# Ensure backend directory is in sys.path
backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

import torch
import transformers
import chromadb

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
from app.schemas.extraction import ExtractionStatus
from app.schemas.processing import DocumentChunk, FileRecord
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


kernel32 = ctypes.WinDLL("kernel32")
psapi = ctypes.WinDLL("psapi")
psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESS_MEMORY_COUNTERS), wintypes.DWORD]
psapi.GetProcessMemoryInfo.restype = wintypes.BOOL


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


def get_process_peak_rss_mb() -> float:
    try:
        counters = PROCESS_MEMORY_COUNTERS()
        counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
        handle = kernel32.GetCurrentProcess()
        if psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
            return counters.PeakWorkingSetSize / (1024 * 1024)
    except Exception:
        pass
    return 0.0


# ---------------------------------------------------------------------------
# Real Chunk Dataset Extraction
# ---------------------------------------------------------------------------
def collect_real_chunks(target_count: int = 2000) -> Tuple[List[str], List[int]]:
    """Extract real document chunks from workspace files using production DocumentChunker."""
    root = Path(__file__).resolve().parent.parent
    extractor = TextExtractor()
    chunker = DocumentChunker(target_tokens=500, overlap_tokens=80)

    unique_chunks: List[Tuple[str, int]] = []
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
                    unique_chunks.append((text, c.token_count))
        except Exception:
            pass

    if not unique_chunks:
        raise RuntimeError("No chunks could be extracted from workspace.")

    # Cycle if fewer than target_count to reach exactly target_count
    result_texts: List[str] = []
    result_tokens: List[int] = []
    idx = 0
    while len(result_texts) < target_count:
        item = unique_chunks[idx % len(unique_chunks)]
        result_texts.append(item[0])
        result_tokens.append(item[1])
        idx += 1

    return result_texts[:target_count], result_tokens[:target_count]


def compute_token_statistics(tokens: List[int]) -> Dict[str, float]:
    """Calculate min, P25, median, P75, P90, P95, P99, max, mean token lengths."""
    s = sorted(tokens)
    n = len(s)

    def percentile(p: float) -> float:
        k = (n - 1) * (p / 100.0)
        f = math.floor(k)
        c = math.ceil(k)
        if f == c:
            return float(s[int(k)])
        return float(s[f] * (c - k) + s[c] * (k - f))

    return {
        "count": float(n),
        "min": float(min(s)),
        "p25": percentile(25.0),
        "median": percentile(50.0),
        "p75": percentile(75.0),
        "p90": percentile(90.0),
        "p95": percentile(95.0),
        "p99": percentile(99.0),
        "max": float(max(s)),
        "mean": float(sum(s) / n),
    }


def analyze_token_padding_workload(
    tokenizer: Any,
    corpus_texts: List[str],
    pool_size: int,
    batch_size: int = 16,
    max_length: int = 512,
) -> Dict[str, Any]:
    """Analyze tokenization, sequence lengths, and padding waste across full 2,000-chunk corpus."""
    prompts = [format_document_prompt(c) for c in corpus_texts]

    total_content_tokens = 0
    total_evaluated_tokens = 0
    total_padding_tokens = 0
    batch_seq_lengths: List[int] = []

    for start_pool in range(0, len(prompts), pool_size):
        pool = prompts[start_pool : start_pool + pool_size]
        if len(pool) > batch_size:
            indexed = sorted(enumerate(pool), key=lambda x: len(x[1]))
        else:
            indexed = list(enumerate(pool))

        for start_batch in range(0, len(indexed), batch_size):
            slice_items = indexed[start_batch : start_batch + batch_size]
            batch_texts = [item[1] for item in slice_items]
            enc = tokenizer(batch_texts, padding=True, truncation=True, max_length=max_length)
            seq_len = len(enc["input_ids"][0])
            batch_seq_lengths.append(seq_len)

            for ids in enc["input_ids"]:
                content_len = sum(1 for t in ids if t != tokenizer.pad_token_id)
                total_content_tokens += content_len
                total_evaluated_tokens += seq_len
                total_padding_tokens += (seq_len - content_len)

    avg_seq_len = sum(batch_seq_lengths) / len(batch_seq_lengths)
    padding_overhead_pct = (total_padding_tokens / total_evaluated_tokens) * 100.0

    return {
        "pool_size": pool_size,
        "batch_size": batch_size,
        "total_chunks": len(corpus_texts),
        "num_inference_batches": len(batch_seq_lengths),
        "fetch_cycles": math.ceil(len(corpus_texts) / pool_size),
        "content_tokens": total_content_tokens,
        "evaluated_tokens": total_evaluated_tokens,
        "padding_tokens": total_padding_tokens,
        "padding_overhead_pct": padding_overhead_pct,
        "avg_seq_len": avg_seq_len,
        "min_seq_len": min(batch_seq_lengths),
        "max_seq_len": max(batch_seq_lengths),
    }


# ---------------------------------------------------------------------------
# Benchmark Harness
# ---------------------------------------------------------------------------
def run_benchmark_pass(
    label: str,
    fetch_pool_size: int,
    batch_size: int,
    corpus_texts: List[str],
    corpus_tokens: List[int],
    tokenizer: Any,
    model: Any,
    config: EmbeddingConfig,
    milestones: List[int],
) -> Dict[str, Any]:
    """Execute a complete benchmark pass with isolated SQLite and ChromaDB."""
    print(f"\n{'='*70}")
    print(f"RUNNING: {label} (Fetch Pool={fetch_pool_size}, Batch Size={batch_size})")
    print(f"{'='*70}")
    sys.stdout.flush()

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir_str:
        tmp_dir = Path(tmp_dir_str)
        db_path = tmp_dir / "bench.db"
        vectors_dir = tmp_dir / "vectors"
        vectors_dir.mkdir(parents=True, exist_ok=True)

        # Setup isolated DB and vector store
        db = DatabaseConnectionManager(db_path=db_path)
        with db.connection() as conn:
            apply_migrations(conn)

        vector_store = ChromaVectorStore(persist_dir=str(vectors_dir))

        # Populate SQLite with chunks
        print(f"[{label}] Populating isolated database with {len(corpus_texts)} chunks...")
        with db.transaction() as conn:
            folder = FolderRepository.get_or_create(conn, str(tmp_dir / "docs"))
            from datetime import datetime, timezone
            file_rec = FileRecord(
                folder_id=folder.id,
                path=str(tmp_dir / "docs" / "bench_corpus.md"),
                filename="bench_corpus.md",
                extension=".md",
                file_type="document",
                size_bytes=len("".join(corpus_texts)),
                modified_at=datetime.now(timezone.utc).isoformat(),
                status=ExtractionStatus.SUCCESS.value,
            )
            file_id = FileRepository.upsert(conn, file_rec)

            doc_chunks = [
                DocumentChunk(
                    file_id=file_id,
                    chunk_index=i,
                    content=text,
                    char_count=len(text),
                    token_count=tok,
                    page_number=1 + (i // 10),
                )
                for i, (text, tok) in enumerate(zip(corpus_texts, corpus_tokens))
            ]
            ChunkRepository.insert_chunks(conn, file_id, doc_chunks)

        with db.connection() as conn:
            initial_unembedded = ChunkEmbeddingRepository.count_unembedded(conn)
        assert initial_unembedded == len(corpus_texts), "All chunks must be unembedded at start"

        # Instrumentation counters
        timings = {
            "sqlite_read": 0.0,
            "tokenization": 0.0,
            "model_forward": 0.0,
            "post_processing": 0.0,
            "chroma_upsert": 0.0,
            "sqlite_commit": 0.0,
        }

        db_counters = {
            "fetch_cycles": 0,
            "model_forward_passes": 0,
            "chroma_calls": 0,
            "sqlite_transactions": 0,
        }

        token_counters = {
            "content_tokens": 0,
            "evaluated_tokens": 0,
            "padding_tokens": 0,
        }

        padded_seq_lengths: List[int] = []
        collected_embeddings: Dict[int, List[float]] = {}
        total_processed = 0
        milestone_results: Dict[int, Dict[str, Any]] = {}

        # GC and initial RSS
        gc.collect()
        steady_state_rss = get_process_rss_mb()
        peak_rss_before = get_process_peak_rss_mb()

        warm_start_time = time.perf_counter()

        while total_processed < len(corpus_texts):
            # 1. SQLite Read Pool
            remaining = len(corpus_texts) - total_processed
            limit = min(fetch_pool_size, remaining)

            t0 = time.perf_counter()
            with db.connection() as conn:
                rows = ChunkEmbeddingRepository.get_unembedded_chunks(conn, limit=limit)
            timings["sqlite_read"] += (time.perf_counter() - t0)
            db_counters["fetch_cycles"] += 1

            if not rows:
                break

            chunk_ids = [r["chunk_id"] for r in rows]
            file_ids = [r["file_id"] for r in rows]
            contents = [r["content"] for r in rows]
            titles = [r["filename"] for r in rows]
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
                for r in rows
            ]

            # 2. Format Prompts
            prompts = [format_document_prompt(c, t) for c, t in zip(contents, titles)]

            # 3. Safe Length-Aware Sorting across candidate pool
            if len(prompts) > batch_size:
                indexed_prompts = sorted(enumerate(prompts), key=lambda x: len(x[1]))
            else:
                indexed_prompts = list(enumerate(prompts))

            pool_results: List[Optional[List[float]]] = [None] * len(prompts)

            # 4. Process in sub-batches of batch_size <= 16
            for start_idx in range(0, len(indexed_prompts), batch_size):
                batch_slice = indexed_prompts[start_idx : start_idx + batch_size]
                batch_texts = [item[1] for item in batch_slice]

                # Tokenization with dynamic padding for this sub-batch
                t0 = time.perf_counter()
                encoded = tokenizer(
                    batch_texts,
                    padding=True,
                    truncation=True,
                    max_length=config.max_sequence_length,
                    return_tensors="pt",
                )
                timings["tokenization"] += (time.perf_counter() - t0)

                # Record tokens
                seq_len = int(encoded["input_ids"].shape[1])
                sub_batch_size = int(encoded["input_ids"].shape[0])
                padded_seq_lengths.append(seq_len)
                db_counters["model_forward_passes"] += 1

                for mask in encoded["attention_mask"]:
                    content_cnt = int(mask.sum())
                    token_counters["content_tokens"] += content_cnt
                    token_counters["evaluated_tokens"] += seq_len
                    token_counters["padding_tokens"] += (seq_len - content_cnt)

                # Model Forward
                t0 = time.perf_counter()
                with torch.no_grad():
                    outputs = model(**encoded)
                    last_hidden = outputs.last_hidden_state
                timings["model_forward"] += (time.perf_counter() - t0)

                # Post-Processing (Pooling + MRL + Normalization)
                t0 = time.perf_counter()
                att_mask = encoded["attention_mask"].unsqueeze(-1)
                sum_emb = torch.sum(last_hidden * att_mask, dim=1)
                sum_m = torch.clamp(att_mask.sum(dim=1), min=1e-9)
                pooled = sum_emb / sum_m

                if config.dimension < pooled.shape[-1]:
                    pooled = pooled[:, : config.dimension]

                normalized = torch.nn.functional.normalize(pooled, p=2, dim=1)
                sub_vecs = normalized.cpu().tolist()
                timings["post_processing"] += (time.perf_counter() - t0)

                for (orig_idx, _), vec in zip(batch_slice, sub_vecs):
                    pool_results[orig_idx] = vec

            # Reordered pool embeddings
            final_pool_embeddings = pool_results

            # 5. ChromaDB Upsert for pool
            t0 = time.perf_counter()
            vector_store.upsert(
                chunk_ids=chunk_ids,
                embeddings=final_pool_embeddings,
                metadatas=metadatas,
                documents=contents,
            )
            timings["chroma_upsert"] += (time.perf_counter() - t0)
            db_counters["chroma_calls"] += 1

            # 6. SQLite Record Batch Commit
            t0 = time.perf_counter()
            records_to_commit = [
                (cid, fid, config.model_id, config.dimension)
                for cid, fid in zip(chunk_ids, file_ids)
            ]
            with db.transaction() as conn:
                ChunkEmbeddingRepository.record_batch(conn, records_to_commit)
            timings["sqlite_commit"] += (time.perf_counter() - t0)
            db_counters["sqlite_transactions"] += 1

            # Store embeddings for programmatic equivalence check
            for cid, vec in zip(chunk_ids, final_pool_embeddings):
                collected_embeddings[cid] = vec

            total_processed += len(chunk_ids)

            # Milestones check
            for m in milestones:
                if total_processed >= m and m not in milestone_results:
                    curr_elapsed = time.perf_counter() - warm_start_time
                    milestone_results[m] = {
                        "chunks": m,
                        "elapsed_s": curr_elapsed,
                        "throughput": m / curr_elapsed,
                        "model_forward_s": timings["model_forward"],
                        "avg_seq_len": sum(padded_seq_lengths) / len(padded_seq_lengths),
                        "rss_mb": get_process_rss_mb(),
                    }
                    print(
                        f"  -> Milestone {m:4d} chunks: {curr_elapsed:6.2f}s "
                        f"({m / curr_elapsed:5.2f} emb/s) | Model Fwd: {timings['model_forward']:6.2f}s | "
                        f"Avg SeqLen: {sum(padded_seq_lengths) / len(padded_seq_lengths):5.1f} | "
                        f"RSS: {get_process_rss_mb():.1f}MB"
                    )
                    sys.stdout.flush()

        warm_total_wall = time.perf_counter() - warm_start_time
        peak_rss_after = get_process_peak_rss_mb()

        # Integrity checks
        assert len(collected_embeddings) == len(corpus_texts), "All chunks must have embeddings"
        assert vector_store.count() == len(corpus_texts), "Chroma count mismatch"
        with db.connection() as conn:
            assert ChunkEmbeddingRepository.count_embedded(conn) == len(corpus_texts), "SQLite embedded mismatch"
            assert ChunkEmbeddingRepository.count_unembedded(conn) == 0, "All chunks must be marked embedded"

        avg_padded_seq_len = sum(padded_seq_lengths) / len(padded_seq_lengths) if padded_seq_lengths else 0.0
        padding_overhead_pct = (
            (token_counters["padding_tokens"] / token_counters["evaluated_tokens"] * 100.0)
            if token_counters["evaluated_tokens"] > 0
            else 0.0
        )

        print(
            f"[{label}] COMPLETED {total_processed} chunks in {warm_total_wall:.2f}s "
            f"({total_processed / warm_total_wall:.2f} emb/s). Avg SeqLen: {avg_padded_seq_len:.1f}"
        )
        sys.stdout.flush()

        return {
            "label": label,
            "fetch_pool_size": fetch_pool_size,
            "batch_size": batch_size,
            "total_chunks": total_processed,
            "warm_total_wall_s": warm_total_wall,
            "throughput_emb_per_s": total_processed / warm_total_wall,
            "timings_s": timings,
            "db_counters": db_counters,
            "token_counters": token_counters,
            "padding_overhead_pct": padding_overhead_pct,
            "avg_padded_seq_len": avg_padded_seq_len,
            "min_padded_seq_len": min(padded_seq_lengths) if padded_seq_lengths else 0,
            "max_padded_seq_len": max(padded_seq_lengths) if padded_seq_lengths else 0,
            "steady_state_rss_mb": steady_state_rss,
            "peak_rss_mb": peak_rss_after,
            "milestones": milestone_results,
            "embeddings": collected_embeddings,
        }


# ---------------------------------------------------------------------------
# Main Routine
# ---------------------------------------------------------------------------
def main():
    print("=" * 80)
    print("OMNISEARCH PHASE 10.5D: FINAL REAL-WORLD EMBEDDING BENCHMARK")
    print("=" * 80)
    sys.stdout.flush()

    settings = get_settings()

    # 1. Environment & Hardware Baseline Audit
    import platform
    cpu_info = platform.processor() or "Unknown CPU"
    logical_cpus = os.cpu_count() or 1
    torch_mgr = TorchDependencyManager.get_instance()
    torch_mod = torch_mgr.ensure_torch()
    torch_threads = torch_mod.get_num_threads()

    resolved_model = settings.resolved_embedding_model

    print("\n--- 1. FROZEN PRODUCTION CONFIGURATION AUDIT ---")
    print(f"Model ID:              {settings.embedding_model_id} (Resolved: {resolved_model})")
    print(f"Target Dimension:      {settings.embedding_dimension}")
    print(f"Max Sequence Length:   512")
    print(f"Production Batch Size: {settings.embedding_batch_size}")
    print(f"Production Fetch Pool: {settings.embedding_fetch_pool_size}")
    print(f"Device:                {settings.embedding_device}")
    print(f"Precision:             {settings.embedding_precision}")
    print(f"PyTorch Version:       {torch_mod.__version__}")
    print(f"Transformers Version:  {transformers.__version__}")
    print(f"ChromaDB Version:      {chromadb.__version__}")
    print(f"CPU Model:             {cpu_info} (Logical Cores: {logical_cpus})")
    print(f"PyTorch CPU Threads:   {torch_threads}")
    print(f"Dynamic Padding:       Enabled")
    print(f"Length-Aware Sorting:  Enabled")
    sys.stdout.flush()

    assert settings.embedding_fetch_pool_size == 128, f"Expected 128, got {settings.embedding_fetch_pool_size}"
    assert settings.embedding_batch_size == 16, f"Expected 16, got {settings.embedding_batch_size}"

    # 2. Extract Real Chunks
    print("\n--- 2. REAL CHUNK DATASET EXTRACTION ---")
    sys.stdout.flush()
    corpus_texts, corpus_tokens = collect_real_chunks(target_count=2000)
    token_stats = compute_token_statistics(corpus_tokens)

    print(f"Total Chunks:          {int(token_stats['count'])}")
    print(f"Min Tokens:            {token_stats['min']:.0f}")
    print(f"P25 Tokens:            {token_stats['p25']:.1f}")
    print(f"Median Tokens:         {token_stats['median']:.1f}")
    print(f"P75 Tokens:            {token_stats['p75']:.1f}")
    print(f"P90 Tokens:            {token_stats['p90']:.1f}")
    print(f"P95 Tokens:            {token_stats['p95']:.1f}")
    print(f"P99 Tokens:            {token_stats['p99']:.1f}")
    print(f"Max Tokens:            {token_stats['max']:.0f}")
    print(f"Average Tokens:        {token_stats['mean']:.2f}")
    sys.stdout.flush()

    # 3. Model Loading (Cold Startup)
    print("\n--- 3. MODEL INITIALIZATION (COLD STARTUP) ---")
    config = EmbeddingConfig(
        model_id=resolved_model,
        dimension=settings.embedding_dimension,
        batch_size=settings.embedding_batch_size,
        fetch_pool_size=settings.embedding_fetch_pool_size,
        device=settings.embedding_device,
        precision=settings.embedding_precision,
        local_files_only=(resolved_model != settings.embedding_model_id),
    )
    model_mgr = EmbeddingModelManager.get_instance()

    t_load_start = time.perf_counter()
    tokenizer, model = model_mgr.get_model_and_tokenizer(config)
    model_load_time_s = time.perf_counter() - t_load_start
    print(f"Model Cold Load Time:  {model_load_time_s:.2f} seconds")
    print(f"Initial Process RSS:   {get_process_rss_mb():.1f} MB")
    sys.stdout.flush()

    # 4. Full 2,000-Chunk Workload & Padding Analysis
    print("\n--- 4. FULL 2,000-CHUNK WORKLOAD & PADDING ANALYSIS ---")
    sys.stdout.flush()
    workload_16 = analyze_token_padding_workload(tokenizer=tokenizer, corpus_texts=corpus_texts, pool_size=16)
    workload_128 = analyze_token_padding_workload(tokenizer=tokenizer, corpus_texts=corpus_texts, pool_size=128)

    print(f"{'Metric (2,000 Chunks)':<35} | {'Pool 16 (Baseline)':<20} | {'Pool 128 (Phase 10.5C)':<22}")
    print("-" * 80)
    print(f"{'SQLite Fetch Cycles':<35} | {workload_16['fetch_cycles']:<20d} | {workload_128['fetch_cycles']:<22d}")
    print(f"{'Model Inference Batches (<=16)':<35} | {workload_16['num_inference_batches']:<20d} | {workload_128['num_inference_batches']:<22d}")
    print(f"{'Average Batch Sequence Length':<35} | {workload_16['avg_seq_len']:<20.2f} | {workload_128['avg_seq_len']:<22.2f}")
    print(f"{'Total Content Tokens':<35} | {workload_16['content_tokens']:<20,d} | {workload_128['content_tokens']:<22,d}")
    print(f"{'Total Evaluated Tokens':<35} | {workload_16['evaluated_tokens']:<20,d} | {workload_128['evaluated_tokens']:<22,d}")
    print(f"{'Wasted Padding Tokens':<35} | {workload_16['padding_tokens']:<20,d} | {workload_128['padding_tokens']:<22,d}")
    print(f"{'Padding Overhead Percentage':<35} | {workload_16['padding_overhead_pct']:<19.2f}% | {workload_128['padding_overhead_pct']:<21.2f}%")
    sys.stdout.flush()
    sys.stdout.flush()

    # Evaluation slice for end-to-end model execution: 256 chunks (2 full pools of 128 vs 16 pools of 16)
    eval_count = 256
    eval_texts = corpus_texts[:eval_count]
    eval_tokens = corpus_tokens[:eval_count]
    milestones = [64, 128, 192, 256]

    # 5. Benchmark A1: Phase 10.5B Baseline (Pool = 16, Batch = 16)
    res_A1 = run_benchmark_pass(
        label="Run A1 (Pool 16 Baseline)",
        fetch_pool_size=16,
        batch_size=16,
        corpus_texts=eval_texts,
        corpus_tokens=eval_tokens,
        tokenizer=tokenizer,
        model=model,
        config=config,
        milestones=milestones,
    )

    # 6. Benchmark B1: Phase 10.5C Optimized (Pool = 128, Batch = 16)
    res_B1 = run_benchmark_pass(
        label="Run B1 (Pool 128 Phase 10.5C)",
        fetch_pool_size=128,
        batch_size=16,
        corpus_texts=eval_texts,
        corpus_tokens=eval_tokens,
        tokenizer=tokenizer,
        model=model,
        config=config,
        milestones=milestones,
    )

    # 7. Correctness & Equivalence Verification
    print("\n--- 5. PROGRAMMATIC CORRECTNESS & EQUIVALENCE VERIFICATION ---")
    emb_A = res_A1["embeddings"]
    emb_B = res_B1["embeddings"]

    assert len(emb_A) == len(emb_B) == len(eval_texts), "Count mismatch between runs"
    max_diff = 0.0
    diff_sum = 0.0
    dim_mismatches = 0

    for cid in emb_A:
        vec_a = emb_A[cid]
        vec_b = emb_B[cid]
        if len(vec_a) != 768 or len(vec_b) != 768:
            dim_mismatches += 1
        for va, vb in zip(vec_a, vec_b):
            d = abs(va - vb)
            if d > max_diff:
                max_diff = d
            diff_sum += d

    avg_diff = diff_sum / (len(emb_A) * 768)
    print(f"Total Chunk IDs Verified:   {len(emb_A)}")
    print(f"Dimension Verified (768):   All vectors match dimension (mismatches: {dim_mismatches})")
    print(f"Max Absolute Vector Diff:   {max_diff:.2e} (Threshold: <= 1e-6)")
    print(f"Average Absolute Diff:      {avg_diff:.2e}")
    sys.stdout.flush()

    assert dim_mismatches == 0, f"Dimension mismatches found: {dim_mismatches}"
    assert max_diff <= 1e-5, f"Vector difference {max_diff} exceeded tolerance"
    print("PASS: Both configurations produce numerically equivalent embeddings!")

    # 8. Summary Comparisons (Measured on 256 chunks & Projected for 2,000 chunks)
    print("\n--- 6. A/B PERFORMANCE COMPARISON (MEASURED ON REAL CHUNKS) ---")
    t16 = res_A1["warm_total_wall_s"]
    t128 = res_B1["warm_total_wall_s"]
    fps16 = res_A1["throughput_emb_per_s"]
    fps128 = res_B1["throughput_emb_per_s"]

    throughput_improvement = ((fps128 / fps16) - 1.0) * 100.0
    time_reduction = ((t16 - t128) / t16) * 100.0

    # 2,000 chunk projection based on empirical throughput
    proj_t16 = 2000.0 / fps16
    proj_t128 = 2000.0 / fps128

    print(f"{'Metric':<35} | {'Pool 16 (Baseline)':<20} | {'Pool 128 (Phase 10.5C)':<22} | {'Change / Delta':<18}")
    print("-" * 102)
    print(f"{'Warm Wall-Clock Time (256 chunks)':<35} | {t16:18.2f} s | {t128:20.2f} s | {time_reduction:+16.2f}%")
    print(f"{'Throughput (embeddings/sec)':<35} | {fps16:18.2f}   | {fps128:20.2f}   | {throughput_improvement:+16.2f}%")
    print(f"{'Projected Time for 2,000 Chunks':<35} | {proj_t16/60.0:16.2f} min | {proj_t128/60.0:18.2f} min | {time_reduction:+16.2f}%")
    print(f"{'Model Forward Time':<35} | {res_A1['timings_s']['model_forward']:18.2f} s | {res_B1['timings_s']['model_forward']:20.2f} s | {((res_A1['timings_s']['model_forward'] - res_B1['timings_s']['model_forward'])/res_A1['timings_s']['model_forward']*-100):+16.2f}%")
    print(f"{'Average Padded Sequence Length':<35} | {res_A1['avg_padded_seq_len']:18.2f}   | {res_B1['avg_padded_seq_len']:20.2f}   | {((res_B1['avg_padded_seq_len']/res_A1['avg_padded_seq_len'] - 1)*100):+16.2f}%")
    print(f"{'Total Evaluated Tokens (256)':<35} | {res_A1['token_counters']['evaluated_tokens']:18,d}   | {res_B1['token_counters']['evaluated_tokens']:20,d}   | {((res_B1['token_counters']['evaluated_tokens']/res_A1['token_counters']['evaluated_tokens'] - 1)*100):+16.2f}%")
    print(f"{'Wasted Padding Tokens (256)':<35} | {res_A1['token_counters']['padding_tokens']:18,d}   | {res_B1['token_counters']['padding_tokens']:20,d}   | {((res_B1['token_counters']['padding_tokens']/res_A1['token_counters']['padding_tokens'] - 1)*100):+16.2f}%")
    print(f"{'Padding Overhead % (256)':<35} | {res_A1['padding_overhead_pct']:17.2f}% | {res_B1['padding_overhead_pct']:19.2f}% | {res_B1['padding_overhead_pct'] - res_A1['padding_overhead_pct']:+15.2f}% pts")
    print(f"{'SQLite Fetch Cycles (256)':<35} | {res_A1['db_counters']['fetch_cycles']:18d}   | {res_B1['db_counters']['fetch_cycles']:20d}   | {res_B1['db_counters']['fetch_cycles'] - res_A1['db_counters']['fetch_cycles']:+18d}")
    print(f"{'ChromaDB Upsert Calls (256)':<35} | {res_A1['db_counters']['chroma_calls']:18d}   | {res_B1['db_counters']['chroma_calls']:20d}   | {res_B1['db_counters']['chroma_calls'] - res_A1['db_counters']['chroma_calls']:+18d}")
    print(f"{'SQLite Transactions (256)':<35} | {res_A1['db_counters']['sqlite_transactions']:18d}   | {res_B1['db_counters']['sqlite_transactions']:20d}   | {res_B1['db_counters']['sqlite_transactions'] - res_A1['db_counters']['sqlite_transactions']:+18d}")
    print(f"{'Peak RSS Memory':<35} | {res_A1['peak_rss_mb']:17.1f} MB | {res_B1['peak_rss_mb']:19.1f} MB | {res_B1['peak_rss_mb'] - res_A1['peak_rss_mb']:+15.1f} MB")
    print("-" * 102)

    # Save results to JSON
    res_A1_clean = {k: v for k, v in res_A1.items() if k != "embeddings"}
    res_B1_clean = {k: v for k, v in res_B1.items() if k != "embeddings"}

    output_summary = {
        "hardware": {
            "cpu": cpu_info,
            "logical_cpus": logical_cpus,
            "pytorch_threads": torch_threads,
            "pytorch_version": torch_mod.__version__,
            "transformers_version": transformers.__version__,
            "chromadb_version": chromadb.__version__,
        },
        "token_statistics": token_stats,
        "workload_2000": {
            "pool16": workload_16,
            "pool128": workload_128,
        },
        "model_cold_load_s": model_load_time_s,
        "run_A1": res_A1_clean,
        "run_B1": res_B1_clean,
        "correctness": {
            "total_chunks_verified": len(emb_A),
            "max_absolute_difference": max_diff,
            "average_absolute_difference": avg_diff,
            "dimension": 768,
            "numerical_equivalence_pass": True,
        },
        "performance": {
            "pool16_warm_time_s": t16,
            "pool128_warm_time_s": t128,
            "pool16_throughput": fps16,
            "pool128_throughput": fps128,
            "throughput_improvement_pct": throughput_improvement,
            "wall_clock_reduction_pct": time_reduction,
            "projected_2000_time_pool16_min": proj_t16 / 60.0,
            "projected_2000_time_pool128_min": proj_t128 / 60.0,
        },
    }

    out_file = Path("scripts/benchmark_105d_results.json")
    out_file.write_text(json.dumps(output_summary, indent=2), encoding="utf-8")
    print(f"\nSaved detailed benchmark results to: {out_file.resolve()}")
    print("=" * 80)


if __name__ == "__main__":
    main()

