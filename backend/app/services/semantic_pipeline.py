"""Semantic indexing pipeline orchestrating chunk embedding and ChromaDB synchronization."""

import hashlib
import logging
from typing import Dict, List, Optional, Set, Tuple

from app.database.connection import DatabaseConnectionManager
from app.database.repositories.cache import EmbeddingCacheRepository
from app.database.repositories.embeddings import ChunkEmbeddingRepository
from app.embeddings.base import BaseEmbedder
from app.vector_store.chroma import ChromaVectorStore

logger = logging.getLogger(__name__)


class SemanticPipeline:
    """Coordinates embedding generation from SQLite chunks to ChromaDB vector store."""

    def __init__(
        self,
        db: DatabaseConnectionManager,
        embedder: BaseEmbedder,
        vector_store: ChromaVectorStore,
        batch_size: int = 16,
    ) -> None:
        self.db = db
        self.embedder = embedder
        self.vector_store = vector_store
        self.batch_size = batch_size

    def sync_embeddings(self, max_chunks: Optional[int] = None) -> int:
        """Fetch unembedded chunks from SQLite, generate embeddings, and persist to ChromaDB.

        Args:
            max_chunks: Optional maximum number of chunks to process in this run.

        Returns:
            Total number of newly embedded chunks stored.
        """
        total_embedded = 0

        while True:
            limit = self.batch_size
            if max_chunks is not None:
                remaining = max_chunks - total_embedded
                if remaining <= 0:
                    break
                limit = min(limit, remaining)

            with self.db.connection() as conn:
                unembedded_rows = ChunkEmbeddingRepository.get_unembedded_chunks(conn, limit=limit)

            if not unembedded_rows:
                break

            chunk_ids: List[int] = []
            file_ids: List[int] = []
            contents: List[str] = []
            titles: List[Optional[str]] = []
            metadatas: List[dict] = []
            cache_keys: List[str] = []
            content_shas: List[str] = []
            modalities: List[str] = []

            for row in unembedded_rows:
                cid = row["chunk_id"]
                fid = row["file_id"]
                c_content = row["content"]
                fname = row["filename"]
                ftype = row["file_type"]
                folder_id = row["folder_id"]
                c_index = row["chunk_index"]
                fpath = row["file_path"]

                chunk_ids.append(cid)
                file_ids.append(fid)
                contents.append(c_content)
                titles.append(fname)
                metadatas.append({
                    "file_id": fid,
                    "filename": fname,
                    "file_type": ftype,
                    "content_type": ftype if ftype in {"image", "audio", "video"} else "document",
                    "folder_id": folder_id,
                    "chunk_index": c_index,
                    "page_number": row["page_number"],
                    "slide_number": row["slide_number"],
                    "sheet_name": row["sheet_name"],
                    "start_line": row["start_line"],
                    "end_line": row["end_line"],
                    "path": fpath,
                })

                modality = ftype if ftype in {"image", "audio", "video"} else "text"
                modalities.append(modality)

                # Compute content sha
                if modality == "text":
                    c_sha = hashlib.sha256(c_content.encode("utf-8")).hexdigest()
                else:
                    c_sha = (
                        row["file_sha256"]
                        if ("file_sha256" in row.keys() and row["file_sha256"])
                        else hashlib.sha256(fpath.encode("utf-8")).hexdigest()
                    )
                content_shas.append(c_sha)

                # Compute deterministic cache key
                k = EmbeddingCacheRepository.compute_cache_key(
                    content_sha256=c_sha,
                    model_name=self.embedder.model_id,
                    modality=modality,
                    dimensions=self.embedder.dimension,
                )
                cache_keys.append(k)

            # Query persistent cache in SQLite
            with self.db.connection() as conn:
                cached_vectors = EmbeddingCacheRepository.get_batch(conn, cache_keys)

            embeddings: List[Optional[List[float]]] = [None] * len(unembedded_rows)
            new_cache_records: List[Tuple[str, str, str, str, int, List[float]]] = []
            cache_hit_count = 0

            # 1. Populate cache hits
            for i, k in enumerate(cache_keys):
                if k in cached_vectors:
                    embeddings[i] = cached_vectors[k]
                    mod = modalities[i]
                    metadatas[i]["embedding_source"] = "native_multimodal" if mod in {"image", "audio", "video"} else "text"
                    cache_hit_count += 1

            # 2. Gather uncached text chunks for a single efficient batched forward pass
            uncached_text_indices: List[int] = []
            uncached_text_contents: List[str] = []
            uncached_text_titles: List[Optional[str]] = []

            for i in range(len(unembedded_rows)):
                if embeddings[i] is None and modalities[i] == "text":
                    uncached_text_indices.append(i)
                    uncached_text_contents.append(contents[i])
                    uncached_text_titles.append(titles[i])

            if uncached_text_contents:
                batch_vecs = self.embedder.embed_documents(uncached_text_contents, titles=uncached_text_titles)
                for idx, v in zip(uncached_text_indices, batch_vecs):
                    embeddings[idx] = v
                    metadatas[idx]["embedding_source"] = "text"
                    new_cache_records.append((
                        cache_keys[idx],
                        content_shas[idx],
                        self.embedder.model_id,
                        "text",
                        self.embedder.dimension,
                        v,
                    ))

            # 3. Process uncached media files (image, audio, video)
            for i in range(len(unembedded_rows)):
                if embeddings[i] is None:
                    row = unembedded_rows[i]
                    ftype = row["file_type"]
                    fpath = row["file_path"]
                    fname = row["filename"]
                    vec = None
                    emb_source = "native_multimodal"
                    if ftype == "image":
                        try:
                            vec = self.embedder.embed_image(fpath)
                        except Exception as e:
                            logger.warning("Image embedding failed for %s, falling back to text: %s", fname, e)
                            emb_source = "metadata_fallback"
                    elif ftype == "audio":
                        try:
                            vec = self.embedder.embed_audio(fpath)
                        except Exception as e:
                            logger.warning("Audio embedding failed for %s, falling back to text: %s", fname, e)
                            emb_source = "metadata_fallback"
                    elif ftype == "video":
                        try:
                            vec = self.embedder.embed_video(fpath)
                        except Exception as e:
                            logger.warning("Video embedding failed for %s, falling back to text: %s", fname, e)
                            emb_source = "metadata_fallback"

                    if vec is None:
                        # Fallback to document text embedding
                        title = titles[i]
                        content = contents[i]
                        doc_vecs = self.embedder.embed_documents([content], titles=[title])
                        vec = doc_vecs[0]

                    embeddings[i] = vec
                    metadatas[i]["embedding_source"] = emb_source

                    if emb_source == "native_multimodal":
                        new_cache_records.append((
                            cache_keys[i],
                            content_shas[i],
                            self.embedder.model_id,
                            ftype,
                            self.embedder.dimension,
                            vec,
                        ))

            # Persist newly computed vectors to SQLite embedding cache
            if new_cache_records:
                with self.db.transaction() as conn:
                    EmbeddingCacheRepository.put_batch(conn, new_cache_records)

            if cache_hit_count > 0:
                logger.info(
                    "Embedding cache: %d hit(s), %d newly computed",
                    cache_hit_count,
                    len(unembedded_rows) - cache_hit_count,
                )

            # Store in ChromaDB
            self.vector_store.upsert(
                chunk_ids=chunk_ids,
                embeddings=embeddings,
                metadatas=metadatas,
                documents=contents,
            )

            # Record in SQLite chunk_embeddings table
            records_to_commit: List[Tuple[int, int, str, int]] = [
                (cid, fid, self.embedder.model_id, self.embedder.dimension)
                for cid, fid in zip(chunk_ids, file_ids)
            ]
            with self.db.transaction() as conn:
                ChunkEmbeddingRepository.record_batch(conn, records_to_commit)

            total_embedded += len(chunk_ids)
            logger.info("Embedded and synced %d chunks (total so far: %d)", len(chunk_ids), total_embedded)

        return total_embedded

    def reconcile_vector_store(self) -> int:
        """Identify and remove vectors in ChromaDB that no longer exist in SQLite chunks table.

        Returns:
            Number of orphaned vectors removed from ChromaDB.
        """
        chroma_ids = self.vector_store.get_all_chunk_ids()
        if not chroma_ids:
            return 0

        with self.db.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM chunks;")
            valid_chunk_ids = {row[0] for row in cursor.fetchall()}
            cursor.close()

        orphaned = chroma_ids - valid_chunk_ids
        if orphaned:
            logger.info("Found %d orphaned vectors in ChromaDB. Deleting...", len(orphaned))
            self.vector_store.delete(list(orphaned))
            with self.db.transaction() as conn:
                for oid in orphaned:
                    ChunkEmbeddingRepository.delete_by_chunk_id(conn, oid)

        return len(orphaned)

    def delete_file_embeddings(self, file_id: int) -> None:
        """Remove all vector embeddings for a given file ID from both Chroma and SQLite."""
        self.vector_store.delete_by_file_id(file_id)
        with self.db.transaction() as conn:
            ChunkEmbeddingRepository.delete_by_file_id(conn, file_id)

