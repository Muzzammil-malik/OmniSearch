"""Controlled benchmark evaluating PyTorch CPU intra-op thread tuning (2, 4, 6, 8) on EmbeddingGemma 2."""

import os
import sys
import time
from pathlib import Path

# Mask broken scipy
sys.modules["scipy"] = None

backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from app.core.dependencies import TorchDependencyManager
from app.embeddings.configuration import EmbeddingConfig
from app.embeddings.model_manager import EmbeddingModelManager
from app.embeddings.prompts import format_document_prompt


SAMPLE_TEXTS = [
    "OmniSearch local-first desktop multifile search application architecture and system design.",
    "FastAPI provides the high performance asynchronous web API for desktop and local clients.",
    "SQLite with FTS5 enables authoritative full-text indexing, BM25 scoring, and metadata persistence.",
    "ChromaDB delivers persistent vector embeddings storage and fast nearest neighbor cosine similarity search.",
    "EmbeddingGemma 2 produces 768-dimensional multimodal vector representations on local CPU inference.",
    "SentenceTransformers integration provides unified embeddings for documents, images, audio, and video.",
    "File watchers track file creation, modification, and deletion events using watchdog on Windows.",
    "Startup reconciliation scans registered folders and reconciles filesystem state against SQLite records.",
] * 4  # 32 texts = 2 batches of 16


def benchmark_threads():
    torch_mgr = TorchDependencyManager.get_instance()
    torch = torch_mgr.ensure_torch()

    config = EmbeddingConfig()
    mgr = EmbeddingModelManager.get_instance()
    print("Loading model and tokenizer...")
    tokenizer, model = mgr.get_model_and_tokenizer(config)
    device = torch.device(config.device)

    formatted = [format_document_prompt(t) for t in SAMPLE_TEXTS]
    encoded = tokenizer(
        formatted,
        padding=True,
        truncation=True,
        max_length=512,
        return_tensors="pt",
    )
    encoded = {k: v.to(device) for k, v in encoded.items()}

    # Warmup
    with torch.no_grad():
        _ = model(**encoded)

    thread_configs = [2, 4, 6, 8]
    results = {}

    print(f"\nBenchmarking forward inference across thread counts (total 32 items, 2 runs each):")
    for t in thread_configs:
        torch.set_num_threads(t)
        latencies = []
        for run in range(3):
            t0 = time.perf_counter()
            with torch.no_grad():
                outputs = model(**encoded)
                # Force synchronization
                _ = outputs.last_hidden_state.sum().item()
            latencies.append(time.perf_counter() - t0)

        # Discard warmup run, take median of remaining 2
        med_lat = sorted(latencies[1:])[0]
        throughput = len(SAMPLE_TEXTS) / med_lat
        results[t] = {
            "latency": med_lat,
            "throughput": throughput,
            "all_runs": latencies,
        }
        print(f"Threads: {t} | Median Latency: {med_lat:.3f}s | Throughput: {throughput:.2f} emb/s | Runs: {[round(x, 3) for x in latencies]}")

    return results


if __name__ == "__main__":
    benchmark_threads()

