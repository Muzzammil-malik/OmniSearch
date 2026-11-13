"""Semantic search engine powered by ChromaDB vector similarity and EmbeddingGemma 2."""

from collections import defaultdict
import json
import time
from typing import Any, Dict, List, Optional, Set, Union

from app.core.logging import get_logger
from app.database.connection import DatabaseConnectionManager
from app.embeddings.base import BaseEmbedder
from app.schemas.search import (
    SearchFilter,
    SemanticSearchQuery,
    SemanticSearchResponse,
    SemanticSearchResultItem,
)
from app.search.filter_utils import normalize_file_type_filters
from app.search.snippets import SnippetFormatter
from app.vector_store.chroma import ChromaVectorStore

logger = get_logger(__name__)


class SemanticSearchEngine:
    """Production semantic search engine querying ChromaDB and joining SQLite metadata."""

    def __init__(
        self,
        db: DatabaseConnectionManager,
        vector_store: ChromaVectorStore,
        embedder: BaseEmbedder,
    ) -> None:
        self.db = db
        self.vector_store = vector_store
        self.embedder = embedder

    def search(
        self,
        query: Union[str, SemanticSearchQuery],
        filters: Optional[SearchFilter] = None,
        limit: int = 20,
        offset: int = 0,
        min_similarity: float = 0.0,
    ) -> SemanticSearchResponse:
        """Execute a semantic vector search across indexed document chunks.

        Args:
            query: User natural language search query string or SemanticSearchQuery.
            filters: Optional search filters.
            limit: Maximum result items to return.
            offset: Pagination offset.
            min_similarity: Minimum cosine similarity threshold [-1.0, 1.0].

        Returns:
            SemanticSearchResponse containing ranked SemanticSearchResultItems.
        """
        start_time = time.perf_counter()

        if isinstance(query, SemanticSearchQuery):
            search_req = query
        else:
            search_req = SemanticSearchQuery(
                query=query,
                filter=filters,
                limit=limit,
                offset=offset,
                min_similarity=min_similarity,
            )

        clean_query = search_req.query.strip()
        if not clean_query:
            return SemanticSearchResponse(
                query=search_req.query,
                total_results=0,
                results=[],
                limit=search_req.limit,
                offset=search_req.offset,
                execution_time_ms=0.0,
                model_id=self.embedder.model_id,
            )

        # 1. Generate query embedding vector
        query_vector = self.embedder.embed_query(clean_query)

        # 2. Build Chroma metadata where filter
        chroma_where = self._build_chroma_filter(search_req.filter)

        # Candidate limit: query more vectors than final limit to accommodate filtering and deduplication
        max_chunks_per_file = (
            search_req.filter.max_chunks_per_file
            if search_req.filter and search_req.filter.max_chunks_per_file
            else 3
        )
        candidate_limit = max((search_req.limit + search_req.offset) * 5, 100)

        # 3. Retrieve nearest neighbor vector matches from ChromaDB
        matches = self.vector_store.query(
            query_embedding=query_vector,
            n_results=candidate_limit,
            where=chroma_where,
        )

        if not matches:
            duration_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
            return SemanticSearchResponse(
                query=search_req.query,
                total_results=0,
                results=[],
                limit=search_req.limit,
                offset=search_req.offset,
                execution_time_ms=duration_ms,
                model_id=self.embedder.model_id,
            )

        # 4. Filter by min_similarity
        filtered_matches = [
            m for m in matches if m["similarity"] >= search_req.min_similarity
        ]

        # 5. Extract chunk IDs and load full SQLite metadata
        matched_chunk_ids = [m["chunk_id"] for m in filtered_matches]
        sqlite_records = self._load_chunk_records(matched_chunk_ids)

        # 6. Apply max_chunks_per_file consolidation and build result items
        results_list: List[SemanticSearchResultItem] = []
        chunks_per_file: Dict[int, int] = defaultdict(int)
        allowed_types: Optional[Set[str]] = None
        if search_req.filter and search_req.filter.file_types:
            norm_list = normalize_file_type_filters(search_req.filter.file_types)
            if norm_list:
                allowed_types = set(norm_list)

        for match in filtered_matches:
            cid = match["chunk_id"]
            rec = sqlite_records.get(cid)
            if not rec:
                continue

            if allowed_types is not None and rec["file_type"] not in allowed_types:
                continue

            file_id = rec["file_id"]
            if chunks_per_file[file_id] >= max_chunks_per_file:
                continue

            chunks_per_file[file_id] += 1

            # Determine stale status
            is_stale = rec["file_status"] != "success"

            # Contextual snippet
            content = rec["content"]
            snippet, _ = SnippetFormatter.format(None, fallback_content=content, max_length=240)

            # Cosine similarity and normalized score [0.0, 1.0]
            similarity = match["similarity"]
            distance = match["distance"]
            normalized_score = round(max(0.0, min(1.0, (similarity + 1.0) / 2.0)), 4)

            custom_meta: Dict[str, Any] = {}
            if rec.get("chunk_meta"):
                try:
                    custom_meta = json.loads(rec["chunk_meta"])
                except Exception:
                    pass

            file_meta: Dict[str, Any] = {}
            if rec.get("file_meta"):
                try:
                    file_meta = json.loads(rec["file_meta"])
                except Exception:
                    pass

            ftype = rec["file_type"]
            content_type = ftype if ftype in {"image", "audio", "video"} else "document"
            media_metadata = file_meta if content_type in {"image", "audio", "video"} else None

            chroma_meta = match.get("metadata", {}) or {}
            emb_source = chroma_meta.get("embedding_source")
            if not emb_source:
                emb_source = "native_multimodal" if content_type in {"image", "audio", "video"} else "text"

            item = SemanticSearchResultItem(
                file_id=file_id,
                chunk_id=cid,
                filename=rec["filename"],
                file_path=rec["file_path"],
                file_type=ftype,
                content_type=content_type,
                file_status=rec["file_status"],
                is_stale=is_stale,
                chunk_index=rec["chunk_index"],
                content=content,
                snippet=snippet,
                score=normalized_score,
                cosine_similarity=round(similarity, 4),
                distance=round(distance, 4),
                page_number=rec.get("page_number"),
                slide_number=rec.get("slide_number"),
                sheet_name=rec.get("sheet_name"),
                row_number=rec.get("row_number"),
                start_line=rec.get("start_line"),
                end_line=rec.get("end_line"),
                metadata=custom_meta,
                media_metadata=media_metadata,
                embedding_source=emb_source,
            )
            results_list.append(item)

        total_matching = len(results_list)
        paginated_results = results_list[search_req.offset : search_req.offset + search_req.limit]

        duration_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
        logger.info(
            "Semantic search for '%s' returned %d results in %.2fms (total matches: %d)",
            clean_query,
            len(paginated_results),
            duration_ms,
            total_matching,
        )

        return SemanticSearchResponse(
            query=search_req.query,
            total_results=total_matching,
            results=paginated_results,
            limit=search_req.limit,
            offset=search_req.offset,
            execution_time_ms=duration_ms,
            model_id=self.embedder.model_id,
        )

    def _build_chroma_filter(self, filters: Optional[SearchFilter]) -> Optional[Dict[str, Any]]:
        """Construct ChromaDB-compatible `where` filter condition from SearchFilter."""
        if not filters:
            return None

        conditions: List[Dict[str, Any]] = []

        if filters.file_types:
            clean_types = normalize_file_type_filters(filters.file_types)
            if clean_types:
                if len(clean_types) == 1:
                    conditions.append({"file_type": clean_types[0]})
                elif len(clean_types) > 1:
                    conditions.append({"file_type": {"$in": clean_types}})

        if filters.folder_ids:
            if len(filters.folder_ids) == 1:
                conditions.append({"folder_id": filters.folder_ids[0]})
            elif len(filters.folder_ids) > 1:
                conditions.append({"folder_id": {"$in": filters.folder_ids}})

        if not conditions:
            return None
        if len(conditions) == 1:
            return conditions[0]
        return {"$and": conditions}

    def _load_chunk_records(self, chunk_ids: List[int]) -> Dict[int, Dict[str, Any]]:
        """Load chunk and file records from SQLite in a single batch query."""
        if not chunk_ids:
            return {}

        placeholders = ",".join("?" for _ in chunk_ids)
        query = f"""
        SELECT c.id AS chunk_id, c.file_id, c.chunk_index, c.content, c.metadata_json AS chunk_meta,
               c.page_number, c.slide_number, c.sheet_name, c.row_number, c.start_line, c.end_line,
               f.filename, f.path AS file_path, f.file_type, f.status AS file_status, f.folder_id,
               f.metadata_json AS file_meta
        FROM chunks c
        JOIN files f ON c.file_id = f.id
        WHERE c.id IN ({placeholders});
        """

        with self.db.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, chunk_ids)
            rows = cursor.fetchall()
            cursor.close()

        records: Dict[int, Dict[str, Any]] = {}
        for r in rows:
            records[r["chunk_id"]] = dict(r)

        return records

