#!/usr/bin/env python3
"""OmniSearch Semantic Embedding Backfill Script.

Synchronizes all unembedded document chunks from SQLite into ChromaDB
using the verified local Google EmbeddingGemma 2 model.
"""

from datetime import datetime, timezone
from pathlib import Path
import sys
import time
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import torch
# Maximize CPU core utilization on host
torch.set_num_threads(min(8, torch.get_num_threads() * 2 if hasattr(torch, "get_num_threads") else 8))

from app.core.config import get_settings
from app.database.connection import DatabaseConnectionManager
from app.database.repositories.embeddings import ChunkEmbeddingRepository
from app.embeddings.configuration import EmbeddingConfig
from app.embeddings.embedder import EmbeddingGemmaEmbedder
from app.services.semantic_pipeline import SemanticPipeline
from app.vector_store.chroma import ChromaVectorStore


def run_backfill(batch_size: int = 16, max_chunks: Optional[int] = None) -> None:
    settings = get_settings()
    db = DatabaseConnectionManager()
    vector_store = ChromaVectorStore(persist_dir=settings.vectors_dir)

    with db.connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM chunks;")
        total_chunks = cursor.fetchone()[0]
        cursor.close()
        unembedded_total = ChunkEmbeddingRepository.count_unembedded(conn)

    initial_chroma = vector_store.count()

    print("=" * 70)
    print("  OMNISEARCH SEMANTIC EMBEDDING BACKFILL")
    print("=" * 70)
    print(f"  Total Chunks in SQLite : {total_chunks:,}")
    print(f"  Currently Embedded     : {initial_chroma:,}")
    print(f"  Pending Embeddings     : {unembedded_total:,}")
    print(f"  Batch Size             : {batch_size}")
    if max_chunks:
        print(f"  Processing Limit       : {max_chunks:,} chunks")
    print("=" * 70)

    if unembedded_total == 0:
        print("[Info] All chunks are already embedded in ChromaDB. Nothing to backfill!")
        return

    resolved_model = settings.resolved_embedding_model
    config = EmbeddingConfig(
        model_id=resolved_model,
        dimension=settings.embedding_dimension,
        batch_size=batch_size,
        device=settings.embedding_device,
        precision=settings.embedding_precision,
        local_files_only=(resolved_model != settings.embedding_model_id),
    )

    print("\nLoading EmbeddingGemma 2 model from local weights...")
    t_load = time.perf_counter()
    embedder = EmbeddingGemmaEmbedder(config=config)
    pipeline = SemanticPipeline(db=db, embedder=embedder, vector_store=vector_store, batch_size=batch_size)
    print(f"Model ready in {time.perf_counter() - t_load:.2f}s.\n")

    target_to_process = min(unembedded_total, max_chunks) if max_chunks else unembedded_total
    total_processed = 0
    t_start = time.perf_counter()

    print(f"Starting embedding generation for {target_to_process:,} chunks...\n")

    try:
        while total_processed < target_to_process:
            step_limit = min(batch_size, target_to_process - total_processed)
            batch_t0 = time.perf_counter()
            count = pipeline.sync_embeddings(max_chunks=step_limit)
            if count == 0:
                break
            total_processed += count
            batch_dur = time.perf_counter() - batch_t0
            elapsed = time.perf_counter() - t_start
            rate = total_processed / elapsed if elapsed > 0 else 0
            eta_sec = (target_to_process - total_processed) / rate if rate > 0 else 0

            print(
                f"[{datetime.now().strftime('%H:%M:%S')}] "
                f"Processed {total_processed:,}/{target_to_process:,} chunks "
                f"({total_processed/target_to_process*100:5.1f}%) | "
                f"Batch: {batch_dur:.1f}s | "
                f"Rate: {rate:.2f} chunks/s | "
                f"ETA: {eta_sec/60:4.1f} min"
            )

    except KeyboardInterrupt:
        print("\n[Interrupted] Backfill paused by user. All completed batches were safely committed.")

    t_end = time.perf_counter()
    final_chroma = vector_store.count()
    with db.connection() as conn:
        final_unembedded = ChunkEmbeddingRepository.count_unembedded(conn)

    print("\n" + "=" * 70)
    print("  BACKFILL SUMMARY")
    print("=" * 70)
    print(f"  Chunks Embedded This Run : {total_processed:,}")
    print(f"  Total Chunks in ChromaDB : {final_chroma:,} / {total_chunks:,}")
    print(f"  Remaining Unembedded     : {final_unembedded:,}")
    print(f"  Total Time Elapsed       : {(t_end - t_start)/60:.2f} minutes")
    print("=" * 70)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Backfill document chunk embeddings into ChromaDB")
    parser.add_argument("--batch-size", type=int, default=16, help="Batch size for embedding generation")
    parser.add_argument("--max-chunks", type=int, default=None, help="Optional maximum chunks to process")
    args = parser.parse_args()

    run_backfill(batch_size=args.batch_size, max_chunks=args.max_chunks)
