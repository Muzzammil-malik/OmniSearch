"""OmniSearch Phase 10.5A — Embedding Performance Profiling & Bottleneck Diagnosis.

Measures all pipeline stages separately without altering production configuration:
1. Cold vs Warm Model Initialization
2. Input Preparation / Prompt Formatting / Tokenization
3. Pure Model Inference
4. Post-processing (Mean Pooling, MRL truncation, L2 Normalization, tolist)
5. ChromaDB Vector Persistence
6. SQLite Metadata Persistence
7. Batch Size Scaling (1, 4, 8, 16, 32)
8. Storage vs Model Compute Isolation
9. CPU Threading & Native Diagnostics
"""

import math
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

# Detect if scipy is blocked by Windows Application Control Policy
scipy_blocked = False
try:
    import scipy
except Exception as _e:
    scipy_blocked = True
    # Mask broken/blocked scipy so transformers does not attempt object-detection loss imports
    sys.modules["scipy"] = None

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from app.core.config import get_settings
from app.core.dependencies import (
    ChromaDependencyManager,
    TorchDependencyManager,
    classify_native_error,
)
from app.database.connection import DatabaseConnectionManager
from app.database.migrations import apply_migrations
from app.database.repositories.chunks import ChunkRepository
from app.database.repositories.embeddings import ChunkEmbeddingRepository
from app.database.repositories.files import FileRepository
from app.database.repositories.folders import FolderRepository
from app.embeddings.configuration import EmbeddingConfig
from app.embeddings.model_manager import EmbeddingModelManager
from app.embeddings.prompts import format_document_prompt
from app.schemas.extraction import ExtractionStatus
from app.schemas.processing import DocumentChunk, FileRecord
from app.vector_store.chroma import ChromaVectorStore


# Synthetic representative document text samples
SAMPLE_CHUNKS = [
    "OmniSearch local-first desktop multifile search application architecture and system design.",
    "FastAPI provides the high performance asynchronous web API for desktop and local clients.",
    "SQLite with FTS5 enables authoritative full-text indexing, BM25 scoring, and metadata persistence.",
    "ChromaDB delivers persistent vector embeddings storage and fast nearest neighbor cosine similarity search.",
    "EmbeddingGemma 2 produces 768-dimensional multimodal vector representations on local CPU inference.",
    "SentenceTransformers integration provides unified embeddings for documents, images, audio, and video.",
    "File watchers track file creation, modification, and deletion events using watchdog on Windows.",
    "Startup reconciliation scans registered folders and reconciles filesystem state against SQLite records.",
    "Hybrid search fuses SQLite BM25 keyword rankings with ChromaDB semantic vector cosine rankings via RRF.",
    "Reciprocal Rank Fusion with smoothing constant k=60 computes combined rank positions across candidate pools.",
    "PyMuPDF extracts text, layout structures, and embedded images from PDF documents quickly and reliably.",
    "Local OCR processing using Tesseract extracts text from image-only scanned PDFs without cloud dependencies.",
    "Next.js frontend connects to the local FastAPI backend with real-time indexing status and unified search.",
    "Document chunking divides long files into token-bounded segments with configurable inter-chunk overlap.",
    "Windows Code Integrity and Smart App Control policies enforce code signing requirements on native binaries.",
    "Error handling ensures graceful degradation to keyword-only search if vector dependencies are unavailable.",
]


def generate_benchmark_corpus(count: int) -> List[str]:
    """Generate a realistic corpus of document chunk texts of length `count`."""
    corpus: List[str] = []
    sample_len = len(SAMPLE_CHUNKS)
    for i in range(count):
        base_text = SAMPLE_CHUNKS[i % sample_len]
        variation = f" Section {i // sample_len + 1}, paragraph chunk id #{i}: {base_text}"
        corpus.append(variation)
    return corpus


def run_diagnostics() -> Dict[str, Any]:
    """Collect CPU, threading, and native dependency diagnostics."""
    torch_mgr = TorchDependencyManager.get_instance()
    chroma_mgr = ChromaDependencyManager.get_instance()

    torch_avail = torch_mgr.is_available()
    chroma_avail = chroma_mgr.is_available()

    torch_mod = torch_mgr.ensure_torch() if torch_avail else None
    chroma_mod = chroma_mgr.ensure_chromadb() if chroma_avail else None

    # Audit individual native modules
    native_status = {}
    for mod_name in ["numpy", "torch", "tokenizers", "transformers", "chromadb", "grpc"]:
        try:
            m = __import__(mod_name)
            native_status[mod_name] = {"available": True, "version": getattr(m, "__version__", "unknown")}
        except Exception as exc:
            native_status[mod_name] = {"available": False, "error": str(exc), "category": classify_native_error(exc)}

    # Check scipy specifically
    scipy_status = {"available": False, "error": "Import blocked by Windows Application Control Policy (_ccallback_c.pyd)", "category": "application_control_policy_blocked"}

    diag = {
        "python_version": sys.version.split()[0],
        "torch_available": torch_avail,
        "torch_version": torch_mgr.get_version(),
        "chroma_available": chroma_avail,
        "chroma_version": chroma_mgr.get_version(),
        "cpu_count": os.cpu_count(),
        "torch_threads": torch_mod.get_num_threads() if torch_mod else None,
        "torch_interop_threads": torch_mod.get_num_interop_threads() if torch_mod else None,
        "omp_num_threads": os.environ.get("OMP_NUM_THREADS"),
        "mkl_num_threads": os.environ.get("MKL_NUM_THREADS"),
        "native_status": native_status,
        "scipy_status": scipy_status,
    }
    return diag


def profile_model_initialization(config: EmbeddingConfig) -> Dict[str, float]:
    """Measure cold start loading time vs first warm inference."""
    mgr = EmbeddingModelManager()
    mgr.unload()

    torch = TorchDependencyManager.get_instance().ensure_torch()
    from transformers import AutoModel, AutoTokenizer

    # 1. Measure Tokenizer Loading
    t0 = time.perf_counter()
    tokenizer = AutoTokenizer.from_pretrained(
        config.model_id,
        local_files_only=config.local_files_only,
    )
    t_tokenizer = time.perf_counter() - t0

    # 2. Measure Model Loading & Device Allocation
    t0 = time.perf_counter()
    torch_dtype = torch.bfloat16 if config.precision == "bfloat16" else torch.float32
    model = AutoModel.from_pretrained(
        config.model_id,
        torch_dtype=torch_dtype,
        local_files_only=config.local_files_only,
    )
    device = torch.device(config.device)
    model.to(device)
    model.eval()
    t_model = time.perf_counter() - t0

    # 3. Measure Cold Inference (1 sample)
    prompt = format_document_prompt("Cold start warm-up inference test.", "Cold Start")
    t0 = time.perf_counter()
    enc = tokenizer([prompt], padding=True, truncation=True, max_length=512, return_tensors="pt")
    enc = {k: v.to(device) for k, v in enc.items()}
    with torch.no_grad():
        out = model(**enc)
        _ = out.last_hidden_state
    t_cold_inference = time.perf_counter() - t0

    # 4. Measure Warm Inference (1 sample)
    t0 = time.perf_counter()
    enc = tokenizer([prompt], padding=True, truncation=True, max_length=512, return_tensors="pt")
    enc = {k: v.to(device) for k, v in enc.items()}
    with torch.no_grad():
        out = model(**enc)
        _ = out.last_hidden_state
    t_warm_inference = time.perf_counter() - t0

    return {
        "tokenizer_load_sec": t_tokenizer,
        "model_load_sec": t_model,
        "total_init_sec": t_tokenizer + t_model,
        "cold_inference_sec": t_cold_inference,
        "warm_inference_sec": t_warm_inference,
    }


def profile_staged_inference(
    tokenizer: Any,
    model: Any,
    device: Any,
    texts: List[str],
    batch_size: int,
    dimension: int = 768,
) -> Dict[str, Any]:
    """Measure input preparation, pure model compute, and post-processing separately for a given batch size."""
    import torch

    total_chunks = len(texts)
    num_batches = math.ceil(total_chunks / batch_size)

    time_prompt_formatting = 0.0
    time_tokenization = 0.0
    time_tensor_device_transfer = 0.0
    time_model_forward = 0.0
    time_pooling = 0.0
    time_normalization = 0.0
    time_tolist = 0.0

    all_embeddings: List[List[float]] = []

    t_total_start = time.perf_counter()

    for start_idx in range(0, total_chunks, batch_size):
        batch_slice = texts[start_idx : start_idx + batch_size]

        # Stage B1: Prompt formatting
        t0 = time.perf_counter()
        batch_prompts = [format_document_prompt(txt, f"Doc-{start_idx + i}") for i, txt in enumerate(batch_slice)]
        time_prompt_formatting += time.perf_counter() - t0

        # Stage B2: Tokenization & Collation
        t0 = time.perf_counter()
        encoded = tokenizer(
            batch_prompts,
            padding=True,
            truncation=True,
            max_length=512,
            return_tensors="pt",
        )
        time_tokenization += time.perf_counter() - t0

        # Stage B3: Device transfer
        t0 = time.perf_counter()
        encoded = {k: v.to(device) for k, v in encoded.items()}
        time_tensor_device_transfer += time.perf_counter() - t0

        # Stage C: Pure Model Forward Inference
        t0 = time.perf_counter()
        with torch.no_grad():
            outputs = model(**encoded)
            last_hidden = outputs.last_hidden_state
        time_model_forward += time.perf_counter() - t0

        # Stage D1: Attention-weighted Mean Pooling
        t0 = time.perf_counter()
        attention_mask = encoded["attention_mask"].unsqueeze(-1)
        sum_embeddings = torch.sum(last_hidden * attention_mask, dim=1)
        sum_mask = torch.clamp(attention_mask.sum(dim=1), min=1e-9)
        pooled = sum_embeddings / sum_mask

        # MRL truncation
        if dimension < pooled.shape[-1]:
            pooled = pooled[:, :dimension]
        time_pooling += time.perf_counter() - t0

        # Stage D2: L2 Normalization
        t0 = time.perf_counter()
        normalized = torch.nn.functional.normalize(pooled, p=2, dim=1)
        time_normalization += time.perf_counter() - t0

        # Stage D3: Tensor to CPU float list conversion
        t0 = time.perf_counter()
        batch_results = normalized.cpu().tolist()
        time_tolist += time.perf_counter() - t0

        all_embeddings.extend(batch_results)

    t_total_end = time.perf_counter()
    total_time = t_total_end - t_total_start

    # Verify correctness of first sample
    sample_vec = all_embeddings[0]
    sample_norm = math.sqrt(sum(x * x for x in sample_vec))
    all_finite = all(math.isfinite(x) for x in sample_vec)

    return {
        "batch_size": batch_size,
        "total_chunks": total_chunks,
        "num_batches": num_batches,
        "total_compute_sec": total_time,
        "time_prompt_formatting_sec": time_prompt_formatting,
        "time_tokenization_sec": time_tokenization,
        "time_device_transfer_sec": time_tensor_device_transfer,
        "time_model_forward_sec": time_model_forward,
        "time_pooling_sec": time_pooling,
        "time_normalization_sec": time_normalization,
        "time_tolist_sec": time_tolist,
        "embeddings_per_sec": total_chunks / total_time if total_time > 0 else 0.0,
        "ms_per_embedding": (total_time / total_chunks) * 1000.0 if total_chunks > 0 else 0.0,
        "sample_dimension": len(sample_vec),
        "sample_l2_norm": sample_norm,
        "sample_all_finite": all_finite,
        "embeddings": all_embeddings,
    }


def profile_storage_pipeline(
    texts: List[str],
    embeddings: List[List[float]],
    batch_size: int = 16,
) -> Dict[str, float]:
    """Measure ChromaDB and SQLite storage persistence separately using temporary storage."""
    total_chunks = len(texts)

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
        tmp_path = Path(tmp_dir)
        db_file = tmp_path / "benchmark.db"
        chroma_dir = tmp_path / "chroma"

        # Initialize SQLite DB
        db = DatabaseConnectionManager(db_path=db_file)
        with db.transaction() as conn:
            apply_migrations(conn)

        # Setup Folder & File record
        with db.transaction() as conn:
            folder = FolderRepository.get_or_create(conn, str(tmp_path / "bench_folder"))
            file_rec = FileRecord(
                folder_id=folder.id,
                path=str(tmp_path / "bench_folder" / "benchmark_doc.txt"),
                filename="benchmark_doc.txt",
                extension=".txt",
                file_type="text",
                content_type="document",
                sha256="bench_sha256",
                size_bytes=1024,
                modified_at="2026-11-11T00:00:00Z",
                status=ExtractionStatus.SUCCESS.value,
            )
            file_id = FileRepository.upsert(conn, file_rec)

            doc_chunks = [
                DocumentChunk(
                    chunk_index=i,
                    content=txt,
                    token_count=len(txt.split()),
                    char_count=len(txt),
                )
                for i, txt in enumerate(texts)
            ]
            ChunkRepository.insert_chunks(conn, file_id, doc_chunks)
            chunk_records = ChunkRepository.get_by_file_id(conn, file_id)
            chunk_ids = [c.id for c in chunk_records]

        # Initialize ChromaDB Vector Store
        t0 = time.perf_counter()
        vector_store = ChromaVectorStore(persist_dir=chroma_dir, collection_name="benchmark_collection")
        _ = vector_store.collection  # Trigger client & collection lazy-init
        t_chroma_init = time.perf_counter() - t0

        # Stage E: ChromaDB Upsert in batches matching pipeline batch_size
        time_chroma_upsert = 0.0
        time_sqlite_record = 0.0

        for start_idx in range(0, total_chunks, batch_size):
            b_chunk_ids = chunk_ids[start_idx : start_idx + batch_size]
            b_embeddings = embeddings[start_idx : start_idx + batch_size]
            b_texts = texts[start_idx : start_idx + batch_size]
            b_metas = [
                {
                    "file_id": file_id,
                    "filename": "benchmark_doc.txt",
                    "file_type": "text",
                    "content_type": "document",
                    "folder_id": folder.id,
                    "chunk_index": start_idx + i,
                    "path": str(tmp_path / "bench_folder" / "benchmark_doc.txt"),
                }
                for i in range(len(b_chunk_ids))
            ]

            t0 = time.perf_counter()
            vector_store.upsert(
                chunk_ids=b_chunk_ids,
                embeddings=b_embeddings,
                metadatas=b_metas,
                documents=b_texts,
            )
            time_chroma_upsert += time.perf_counter() - t0

            # Stage F: SQLite ChunkEmbeddingRepository.record_batch in transaction
            t0 = time.perf_counter()
            with db.transaction() as conn:
                records_to_commit = [
                    (cid, file_id, "google/embeddinggemma-2", len(b_embeddings[0]))
                    for cid in b_chunk_ids
                ]
                ChunkEmbeddingRepository.record_batch(conn, records_to_commit)
            time_sqlite_record += time.perf_counter() - t0

        chroma_count = vector_store.count()
        assert chroma_count == total_chunks, f"Chroma count {chroma_count} != {total_chunks}"

        return {
            "chroma_init_sec": t_chroma_init,
            "chroma_upsert_sec": time_chroma_upsert,
            "sqlite_record_sec": time_sqlite_record,
            "total_storage_sec": time_chroma_upsert + time_sqlite_record,
        }


def main():
    print("=" * 76, flush=True)
    print(" OmniSearch — Phase 10.5A Embedding Performance Profiler & Bottleneck Diagnosis", flush=True)
    print("=" * 76, flush=True)

    # 1. Diagnostics
    print("\n[Stage 1/6] Running System & Dependency Diagnostics...", flush=True)
    diag = run_diagnostics()
    print(f"  • Python: {diag['python_version']}", flush=True)
    print(f"  • PyTorch: {diag['torch_version']} (Available: {diag['torch_available']})", flush=True)
    print(f"  • ChromaDB: {diag['chroma_version']} (Available: {diag['chroma_available']})", flush=True)
    print(f"  • CPU Cores / Logical Processors: {diag['cpu_count']}", flush=True)
    print(f"  • PyTorch Compute Threads: {diag['torch_threads']}", flush=True)
    print(f"  • PyTorch Interop Threads: {diag['torch_interop_threads']}", flush=True)
    print(f"  • OMP_NUM_THREADS: {diag['omp_num_threads']}, MKL_NUM_THREADS: {diag['mkl_num_threads']}", flush=True)

    settings = get_settings()
    model_path = settings.resolved_embedding_model
    config = EmbeddingConfig(
        model_id=model_path,
        dimension=768,
        batch_size=16,
        device="cpu",
        precision="float32",
        local_files_only=True,
    )
    print(f"  • Embedding Model ID: {config.model_id}", flush=True)
    print(f"  • Target Device: {config.device}, Precision: {config.precision}, Dimension: {config.dimension}", flush=True)

    # 2. Model Initialization (Cold vs Warm)
    print("\n[Stage 2/6] Measuring Model Initialization (Cold vs Warm)...", flush=True)
    init_res = profile_model_initialization(config)
    print(f"  • Tokenizer Load Time : {init_res['tokenizer_load_sec']:.3f}s", flush=True)
    print(f"  • Model Load Time     : {init_res['model_load_sec']:.3f}s", flush=True)
    print(f"  • Total Cold Init     : {init_res['total_init_sec']:.3f}s", flush=True)
    print(f"  • Cold First Inference: {init_res['cold_inference_sec']:.3f}s", flush=True)
    print(f"  • Warm Inference (1x) : {init_res['warm_inference_sec']:.3f}s", flush=True)

    # Load resident model for subsequent benchmark runs
    mgr = EmbeddingModelManager.get_instance()
    tokenizer, model = mgr.get_model_and_tokenizer(config)
    torch = TorchDependencyManager.get_instance().ensure_torch()
    device = torch.device(config.device)

    # 3. Controlled Benchmark (100 Chunks) across Pipeline Stages
    benchmark_size = 100
    print(f"\n[Stage 3/6] Profiling Detailed Pipeline Stages on {benchmark_size} Chunks (Batch Size = 16)...", flush=True)
    corpus_100 = generate_benchmark_corpus(benchmark_size)

    stage_res = profile_staged_inference(
        tokenizer=tokenizer,
        model=model,
        device=device,
        texts=corpus_100,
        batch_size=16,
        dimension=768,
    )
    embeddings_100 = stage_res["embeddings"]

    print("  --- Compute Stage Breakdown (100 Chunks) ---", flush=True)
    print(f"  • Prompt Formatting  : {stage_res['time_prompt_formatting_sec']:.4f}s", flush=True)
    print(f"  • Tokenization        : {stage_res['time_tokenization_sec']:.4f}s", flush=True)
    print(f"  • Tensor Device Copy  : {stage_res['time_device_transfer_sec']:.4f}s", flush=True)
    print(f"  • Model Forward Pass  : {stage_res['time_model_forward_sec']:.4f}s", flush=True)
    print(f"  • Mean Pooling & MRL  : {stage_res['time_pooling_sec']:.4f}s", flush=True)
    print(f"  • L2 Normalization    : {stage_res['time_normalization_sec']:.4f}s", flush=True)
    print(f"  • tolist / CPU Copy   : {stage_res['time_tolist_sec']:.4f}s", flush=True)
    print(f"  • Total Compute Time  : {stage_res['total_compute_sec']:.4f}s", flush=True)
    print(f"  • Throughput          : {stage_res['embeddings_per_sec']:.2f} emb/sec ({stage_res['ms_per_embedding']:.1f} ms/emb)", flush=True)
    print(f"  • Correctness         : dim={stage_res['sample_dimension']}, norm={stage_res['sample_l2_norm']:.4f}, finite={stage_res['sample_all_finite']}", flush=True)

    # 4. Storage Persistence Profiling (ChromaDB + SQLite)
    print(f"\n[Stage 4/6] Profiling Storage Persistence on {benchmark_size} Chunks (ChromaDB + SQLite)...", flush=True)
    storage_res = profile_storage_pipeline(corpus_100, embeddings_100, batch_size=16)
    print(f"  • Chroma Collection Init : {storage_res['chroma_init_sec']:.4f}s", flush=True)
    print(f"  • Chroma Upsert (100x)   : {storage_res['chroma_upsert_sec']:.4f}s", flush=True)
    print(f"  • SQLite Record Batch    : {storage_res['sqlite_record_sec']:.4f}s", flush=True)
    print(f"  • Total Storage Overhead : {storage_res['total_storage_sec']:.4f}s", flush=True)

    # 5. Batch Size Scaling Comparison
    print("\n[Stage 5/6] Measuring Batch Size Scaling (1, 4, 8, 16, 32)...", flush=True)
    batch_sizes = [1, 4, 8, 16, 32]
    batch_results: List[Dict[str, Any]] = []

    # Use 32 chunks for batch scaling to keep profile time fast and predictable
    scale_size = 32
    corpus_scale = generate_benchmark_corpus(scale_size)

    for bs in batch_sizes:
        res = profile_staged_inference(
            tokenizer=tokenizer,
            model=model,
            device=device,
            texts=corpus_scale,
            batch_size=bs,
            dimension=768,
        )
        batch_results.append(res)
        print(f"  • Batch Size {bs:2d}: {res['total_compute_sec']:.2f}s total ({res['time_model_forward_sec']:.2f}s forward), {res['embeddings_per_sec']:.2f} emb/sec, {res['ms_per_embedding']:.1f} ms/emb", flush=True)

    # 6. Overall Bottleneck Table & 2,000 Embeddings Extrapolation
    print("\n[Stage 6/6] Computing Bottleneck Distribution & 2,000 Chunks Projection...", flush=True)
    total_pipeline_100 = stage_res["total_compute_sec"] + storage_res["total_storage_sec"]

    t_formatting = stage_res["time_prompt_formatting_sec"]
    t_tokenization = stage_res["time_tokenization_sec"]
    t_device_copy = stage_res["time_device_transfer_sec"]
    t_forward = stage_res["time_model_forward_sec"]
    t_pooling = stage_res["time_pooling_sec"]
    t_normalization = stage_res["time_normalization_sec"]
    t_tolist = stage_res["time_tolist_sec"]
    t_chroma = storage_res["chroma_upsert_sec"]
    t_sqlite = storage_res["sqlite_record_sec"]

    stages = [
        ("Prompt Formatting", t_formatting),
        ("Tokenization", t_tokenization),
        ("Tensor Device Transfer", t_device_copy),
        ("Model Forward Inference", t_forward),
        ("Mean Pooling & Truncation", t_pooling),
        ("L2 Normalization", t_normalization),
        ("Tensor tolist / Python Conversion", t_tolist),
        ("ChromaDB Upsert", t_chroma),
        ("SQLite Metadata Commit", t_sqlite),
    ]

    print("\n" + "=" * 76, flush=True)
    print(f"{'Pipeline Stage':<35} | {'Time (100 ch)':<12} | {'% Total':<8} | {'Bottleneck?'}", flush=True)
    print("-" * 76, flush=True)
    for name, dur in stages:
        pct = (dur / total_pipeline_100) * 100.0 if total_pipeline_100 > 0 else 0.0
        is_bottleneck = "YES (PRIMARY)" if pct > 50.0 else ("YES (SECONDARY)" if pct > 10.0 else "No")
        print(f"{name:<35} | {dur:9.4f}s    | {pct:6.2f}%  | {is_bottleneck}", flush=True)
    print("-" * 76, flush=True)
    print(f"{'Total Full Pipeline (100 chunks)':<35} | {total_pipeline_100:9.4f}s    | 100.00%  |", flush=True)
    print("=" * 76, flush=True)

    # Extrapolations for 2,000 chunks
    time_2000_sec = (total_pipeline_100 / benchmark_size) * 2000
    time_2000_forward_sec = (t_forward / benchmark_size) * 2000
    time_2000_storage_sec = (storage_res["total_storage_sec"] / benchmark_size) * 2000

    print(f"\n2,000 Chunks Projection (Production Baseline):", flush=True)
    print(f"  • Total Projected Time: {time_2000_sec:.1f}s (~{time_2000_sec / 60.0:.1f} minutes)", flush=True)
    print(f"  • Projected Model Inference Time: {time_2000_forward_sec:.1f}s (~{time_2000_forward_sec / 60.0:.1f} minutes, {t_forward / total_pipeline_100 * 100:.1f}% of total)", flush=True)
    print(f"  • Projected Storage Time: {time_2000_storage_sec:.1f}s (~{time_2000_storage_sec / 60.0:.1f} minutes, {storage_res['total_storage_sec'] / total_pipeline_100 * 100:.1f}% of total)", flush=True)
    print(f"  • Model Compute to Storage Ratio: {(t_forward / storage_res['total_storage_sec']) if storage_res['total_storage_sec'] > 0 else 0.0:.1f} : 1", flush=True)
    print("=" * 76, flush=True)


if __name__ == "__main__":
    main()
