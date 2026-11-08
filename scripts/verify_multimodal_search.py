"""Phase 10 Multimodal Search Engine Verification Script with Real EmbeddingGemma 2.

Tests real local inference across all 4 modalities:
- Text
- Image
- Audio
- Video
Using Google EmbeddingGemma 2 and ChromaDB.
"""

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

# Add backend to sys.path
backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from app.core.config import get_settings
from app.database.initialization import init_db
from app.database.repositories.files import FileRepository
from app.database.repositories.folders import FolderRepository
from app.embeddings.configuration import EmbeddingConfig
from app.embeddings.embedder import EmbeddingGemmaEmbedder
from app.search.hybrid_search import HybridSearchEngine
from app.search.keyword_search import KeywordSearchEngine
from app.search.semantic_search import SemanticSearchEngine
from app.services.indexer import IndexingService
from app.services.semantic_pipeline import SemanticPipeline
from app.vector_store.chroma import ChromaVectorStore


def cosine_sim(a, b):
    a = np.array(a, dtype=np.float32)
    b = np.array(b, dtype=np.float32)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def generate_test_media(tmp_dir: Path):
    """Generate realistic test files for all modalities."""
    media_dir = tmp_dir / "media_library"
    media_dir.mkdir(parents=True, exist_ok=True)

    # 1. Image: Sunset on beach
    img_path = media_dir / "golden_sunset.jpg"
    img = Image.new("RGB", (640, 480), color=(255, 120, 30))
    draw = ImageDraw.Draw(img)
    # Draw yellow sun and blue water
    draw.ellipse((270, 150, 370, 250), fill=(255, 240, 50))
    draw.rectangle((0, 300, 640, 480), fill=(20, 80, 180))
    img.save(img_path, quality=95)

    # 2. Audio: 440Hz acoustic tone WAV
    audio_path = media_dir / "acoustic_tone.wav"
    sample_rate = 16000
    duration_sec = 2.0
    num_samples = int(duration_sec * sample_rate)
    with wave.open(str(audio_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        frames = bytearray()
        for i in range(num_samples):
            # Harmonics
            val1 = math.sin(2.0 * math.pi * 440.0 * i / sample_rate)
            val2 = 0.3 * math.sin(2.0 * math.pi * 880.0 * i / sample_rate)
            sample_val = int(32767.0 * 0.4 * (val1 + val2))
            frames.extend(struct.pack("<h", sample_val))
        wf.writeframes(frames)

    # 3. Text: Technical document
    doc_path = media_dir / "quantum_computing.txt"
    doc_path.write_text(
        "Quantum computing harnesses qubits, superposition, and entanglement to solve discrete optimization problems.",
        encoding="utf-8",
    )

    # 4. Video: Ocean waves MP4
    video_path = media_dir / "ocean_waves.mp4"
    import av
    container = av.open(str(video_path), mode="w")
    stream = container.add_stream("mpeg4", rate=10)
    stream.width = 128
    stream.height = 128
    stream.pix_fmt = "yuv420p"
    for i in range(8):
        base = np.zeros((128, 128, 3), dtype=np.uint8)
        base[:, :, 0] = np.clip(10 + i * 15, 0, 255)
        base[:, :, 1] = np.clip(80 + i * 20, 0, 255)
        base[:, :, 2] = np.clip(180 + i * 8, 0, 255)
        frame = av.VideoFrame.from_ndarray(base, format="rgb24")
        for packet in stream.encode(frame):
            container.mux(packet)
    for packet in stream.encode():
        container.mux(packet)
    container.close()

    return media_dir, img_path, audio_path, doc_path, video_path


def main():
    print("=" * 70)
    print(" OmniSearch — Phase 10 Multimodal Search Engine Real Model Verification")
    print("=" * 70)

    settings = get_settings()
    local_model_path = Path(os.path.expandvars(r"%LOCALAPPDATA%\OmniSearch\models\embeddinggemma-2"))
    if not local_model_path.exists() or not (local_model_path / "model.safetensors").exists():
        print(f"Error: EmbeddingGemma 2 weights not found at {local_model_path}")
        sys.exit(1)

    print(f"\n[1/5] Initializing local EmbeddingGemma 2 from:\n      {local_model_path}")
    t0 = time.perf_counter()
    config = EmbeddingConfig(
        model_id=str(local_model_path),
        dimension=768,
        device="cpu",
        precision="float32",
        local_files_only=True,
    )
    embedder = EmbeddingGemmaEmbedder(config=config)
    t_load = time.perf_counter() - t0
    print(f"      Embedder initialized in {t_load:.2f}s")

    # Temporary directory for test run
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_str:
        tmp_dir = Path(tmp_str)
        media_dir, img_path, audio_path, doc_path, video_path = generate_test_media(tmp_dir)

        print("\n[2/5] Testing direct multimodal embedding generation on CPU:")

        # 1. Query text embedding
        t0 = time.perf_counter()
        q_vec = embedder.embed_query("sunset over the ocean")
        t_q = time.perf_counter() - t0
        print(f"  [Text Query] Shape: {len(q_vec)} | L2 Norm: {np.linalg.norm(q_vec):.4f} | Finite: {np.all(np.isfinite(q_vec))} | Time: {t_q:.2f}s")
        assert len(q_vec) == 768 and np.all(np.isfinite(q_vec)) and abs(np.linalg.norm(q_vec) - 1.0) < 1e-4

        # 2. Image embedding
        t0 = time.perf_counter()
        img_vec = embedder.embed_image(str(img_path))
        t_img = time.perf_counter() - t0
        print(f"  [Image File] Shape: {len(img_vec)} | L2 Norm: {np.linalg.norm(img_vec):.4f} | Finite: {np.all(np.isfinite(img_vec))} | Time: {t_img:.2f}s")
        assert len(img_vec) == 768 and np.all(np.isfinite(img_vec)) and abs(np.linalg.norm(img_vec) - 1.0) < 1e-4

        # 3. Audio embedding
        t0 = time.perf_counter()
        audio_vec = embedder.embed_audio(str(audio_path))
        t_audio = time.perf_counter() - t0
        print(f"  [Audio File] Shape: {len(audio_vec)} | L2 Norm: {np.linalg.norm(audio_vec):.4f} | Finite: {np.all(np.isfinite(audio_vec))} | Time: {t_audio:.2f}s")
        assert len(audio_vec) == 768 and np.all(np.isfinite(audio_vec)) and abs(np.linalg.norm(audio_vec) - 1.0) < 1e-4

        # 4. Video embedding
        t0 = time.perf_counter()
        vid_vec = embedder.embed_video(str(video_path))
        t_vid = time.perf_counter() - t0
        print(f"  [Video File] Shape: {len(vid_vec)} | L2 Norm: {np.linalg.norm(vid_vec):.4f} | Finite: {np.all(np.isfinite(vid_vec))} | Time: {t_vid:.2f}s")
        assert len(vid_vec) == 768 and np.all(np.isfinite(vid_vec)) and abs(np.linalg.norm(vid_vec) - 1.0) < 1e-4

        # Cross-modal cosine similarities
        sim_sunset_img = cosine_sim(q_vec, img_vec)
        sim_sunset_audio = cosine_sim(q_vec, audio_vec)
        print("\n[3/5] Cross-Modal Semantic Similarity Alignment:")
        print(f"  Query: 'sunset over the ocean'")
        print(f"  -> Sunset Image Cosine Similarity: {sim_sunset_img:.4f}")
        print(f"  -> Audio Tone Cosine Similarity:  {sim_sunset_audio:.4f}")
        assert sim_sunset_img > sim_sunset_audio, "Visual sunset match must have higher similarity than audio tone!"
        print("  -> Alignment verified: Sunset image is significantly more similar to query than audio.")

        # Cross-modal query for video
        q_vid_vec = embedder.embed_query("ocean waves moving water")
        sim_video_match = cosine_sim(q_vid_vec, vid_vec)
        sim_audio_mismatch = cosine_sim(q_vid_vec, audio_vec)
        print(f"  Query: 'ocean waves moving water'")
        print(f"  -> Video Clip Cosine Similarity:   {sim_video_match:.4f}")
        print(f"  -> Audio Tone Cosine Similarity:  {sim_audio_mismatch:.4f}")
        assert sim_video_match > sim_audio_mismatch, "Ocean video match must have higher similarity than audio tone!"
        print("  -> Alignment verified: Video clip correctly retrieved by cross-modal semantic query.")

        print("\n[4/5] Testing full indexing pipeline with SQLite & ChromaDB:")
        db_path = tmp_dir / "verify_omnisearch.db"
        vectors_path = tmp_dir / "verify_vectors"
        db = init_db(db_path)
        vector_store = ChromaVectorStore(persist_dir=vectors_path)
        pipeline = SemanticPipeline(db=db, embedder=embedder, vector_store=vector_store)
        indexer = IndexingService(db=db, semantic_pipeline=pipeline)

        with db.connection() as conn:
            f_rec = FolderRepository.get_or_create(conn, str(media_dir))
            f_id = f_rec.id

        t0 = time.perf_counter()
        job = indexer.index_folder(media_dir, generate_embeddings=True)
        t_index = time.perf_counter() - t0
        print(f"  Indexing job status: {job.status} ({job.successful_files} files, {t_index:.2f}s)")
        assert job.status == "completed"
        assert job.successful_files == 4

        with db.connection() as conn:
            indexed_files = FileRepository.list_by_folder(conn, f_id)
            print(f"  SQLite indexed files: {[f.filename for f in indexed_files]}")
        print(f"  ChromaDB vector count: {vector_store.count()}")
        assert vector_store.count() == 4

        print("\n[5/5] Executing Multimodal Unified & Hybrid Search Queries:")
        keyword_engine = KeywordSearchEngine(db=db)
        semantic_engine = SemanticSearchEngine(db=db, vector_store=vector_store, embedder=embedder)
        hybrid_engine = HybridSearchEngine(db=db, keyword_engine=keyword_engine, semantic_engine=semantic_engine)

        # Search 1: "golden sunset" -> Should retrieve image as #1
        res1 = hybrid_engine.search("golden sunset")
        print(f"  Search: 'golden sunset' -> {len(res1.results)} results")
        top_match = res1.results[0]
        print(f"    #1 Rank: {top_match.filename} ({top_match.file_type}) | RRF: {top_match.rrf_score:.4f} | Sim: {top_match.cosine_similarity}")
        assert top_match.filename == "golden_sunset.jpg"
        assert top_match.content_type == "image"
        assert top_match.embedding_source == "native_multimodal"

        # Search 2: "acoustic tone" -> Should retrieve audio as #1
        res2 = hybrid_engine.search("acoustic tone")
        print(f"  Search: 'acoustic tone' -> {len(res2.results)} results")
        top_audio = res2.results[0]
        print(f"    #1 Rank: {top_audio.filename} ({top_audio.file_type}) | RRF: {top_audio.rrf_score:.4f} | Sim: {top_audio.cosine_similarity}")
        assert top_audio.filename == "acoustic_tone.wav"
        assert top_audio.content_type == "audio"
        assert top_audio.embedding_source == "native_multimodal"

        # Search 3: "ocean waves" -> Should retrieve video
        res3 = semantic_engine.search("ocean waves")
        print(f"  Semantic Search: 'ocean waves' -> {len(res3.results)} results")
        vid_results = [r for r in res3.results if r.file_type == "video"]
        assert len(vid_results) == 1
        top_vid = vid_results[0]
        print(f"    Video Result: {top_vid.filename} ({top_vid.content_type}) | Sim: {top_vid.cosine_similarity} | Source: {top_vid.embedding_source}")
        assert top_vid.filename == "ocean_waves.mp4"
        assert top_vid.content_type == "video"
        assert top_vid.embedding_source == "native_multimodal"
        assert top_vid.media_metadata is not None
        assert top_vid.media_metadata.get("width") == 128

        # Video deletion test
        print("\n  Testing Video Lifecycle (Deletion & ChromaDB Vector Cleanup):")
        deleted = indexer.delete_single_file(video_path)
        assert deleted is True
        print(f"    Deleted {video_path.name}: ChromaDB count reduced to {vector_store.count()}")
        assert vector_store.count() == 3
        res_post_delete = semantic_engine.search("ocean waves")
        assert all(r.filename != "ocean_waves.mp4" for r in res_post_delete.results)
        print("    Verified deleted video no longer appears in semantic search results.")

        print("\n" + "=" * 70)
        print(" ALL MULTIMODAL VERIFICATION CHECKS PASSED SUCCESSFULLY!")
        print(" EmbeddingGemma 2 correctly embeds and retrieves text, images, audio, and video")
        print(" in a unified 768-D local vector space.")
        print("=" * 70)
        print(" in a unified 768-D local vector space.")
        print("=" * 70)


if __name__ == "__main__":
    main()
