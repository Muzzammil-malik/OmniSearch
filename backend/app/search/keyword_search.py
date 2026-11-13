"""SQLite FTS5 keyword search engine with BM25 ranking, filtering, and snippet generation."""

import json
import sqlite3
import time
from typing import Any, Dict, List, Optional, Tuple, Union
from app.core.logging import get_logger
from app.database.connection import DatabaseConnectionManager
from app.schemas.search import (
    SearchFilter,
    SearchQuery,
    SearchResponse,
    SearchResultItem,
)
from app.search.filter_utils import normalize_file_type_filters
from app.search.query_parser import QueryParser
from app.search.snippets import SnippetFormatter

logger = get_logger(__name__)


class KeywordSearchEngine:
    """Production-minded keyword search engine powered by SQLite FTS5 and BM25."""

    def __init__(self, db: DatabaseConnectionManager) -> None:
        self.db = db

    def search(
        self,
        query: Union[str, SearchQuery],
        filters: Optional[SearchFilter] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> SearchResponse:
        """Execute a full-text keyword search across indexed document chunks.

        Args:
            query: User query string or structured SearchQuery model.
            filters: Optional search filters (if query is a string).
            limit: Maximum result items to return.
            offset: Pagination offset.

        Returns:
            SearchResponse containing ranked SearchResultItems and query metrics.
        """
        start_time = time.perf_counter()

        # Normalize incoming request
        if isinstance(query, SearchQuery):
            search_req = query
        else:
            search_req = SearchQuery(
                query=query,
                filter=filters,
                limit=limit,
                offset=offset,
            )

        parsed = QueryParser.parse(search_req.query)
        if parsed.is_empty:
            logger.debug("Empty or whitespace search query: '%s'", search_req.query)
            return SearchResponse(
                query=search_req.query,
                total_results=0,
                results=[],
                limit=search_req.limit,
                offset=search_req.offset,
                execution_time_ms=0.0,
            )

        active_filter = search_req.filter or SearchFilter()
        max_chunks_per_file = active_filter.max_chunks_per_file or 3

        with self.db.connection() as conn:
            # Build filter clauses and parameters
            where_clauses, filter_params = self._build_filter_clauses(active_filter)

            # 1. Total matching results count
            total_count = self._get_total_count(
                conn,
                fts_query=parsed.fts_query,
                max_chunks_per_file=max_chunks_per_file,
                where_clauses=where_clauses,
                filter_params=filter_params,
            )

            # 2. Ranked search results
            results = self._fetch_ranked_results(
                conn,
                fts_query=parsed.fts_query,
                parsed_terms=parsed.terms + parsed.phrases,
                max_chunks_per_file=max_chunks_per_file,
                where_clauses=where_clauses,
                filter_params=filter_params,
                limit=search_req.limit,
                offset=search_req.offset,
            )

        duration_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
        logger.info(
            "Search for '%s' returned %d results in %.2fms (total matches: %d)",
            search_req.query,
            len(results),
            duration_ms,
            total_count,
        )

        return SearchResponse(
            query=search_req.query,
            total_results=total_count,
            results=results,
            limit=search_req.limit,
            offset=search_req.offset,
            execution_time_ms=duration_ms,
        )

    def _build_filter_clauses(
        self,
        filter_spec: SearchFilter,
    ) -> Tuple[List[str], List[Any]]:
        """Construct parameterized SQL WHERE subclauses from SearchFilter."""
        clauses: List[str] = []
        params: List[Any] = []

        if filter_spec.file_types:
            clean_types = normalize_file_type_filters(filter_spec.file_types)
            if clean_types:
                placeholders = ", ".join("?" for _ in clean_types)
                clauses.append(f"f.file_type IN ({placeholders})")
                params.extend(clean_types)

        if filter_spec.folder_ids:
            placeholders = ", ".join("?" for _ in filter_spec.folder_ids)
            clauses.append(f"f.folder_id IN ({placeholders})")
            params.extend(filter_spec.folder_ids)

        if filter_spec.folder_paths:
            placeholders = ", ".join("?" for _ in filter_spec.folder_paths)
            clauses.append(f"fld.path IN ({placeholders})")
            params.extend(filter_spec.folder_paths)

        return clauses, params

    def _get_total_count(
        self,
        conn: sqlite3.Connection,
        fts_query: str,
        max_chunks_per_file: int,
        where_clauses: List[str],
        filter_params: List[Any],
    ) -> int:
        """Count total matching rows after duplicate consolidation and filtering."""
        additional_where = ""
        if where_clauses:
            additional_where = " AND " + " AND ".join(where_clauses)

        sql = f"""
        WITH raw_matches AS (
            SELECT chunk_id, file_id,
                   bm25(chunks_fts, 5.0, 2.0, 1.0) AS bm25_score
            FROM chunks_fts
            WHERE chunks_fts MATCH ?
        ),
        ranked AS (
            SELECT chunk_id, file_id,
                   ROW_NUMBER() OVER (
                       PARTITION BY file_id
                       ORDER BY bm25_score ASC, chunk_id ASC
                   ) AS file_rank
            FROM raw_matches
        )
        SELECT COUNT(*)
        FROM ranked r
        JOIN files f ON r.file_id = f.id
        LEFT JOIN folders fld ON f.folder_id = fld.id
        WHERE r.file_rank <= ?
        {additional_where};
        """
        cursor = conn.cursor()
        cursor.execute(sql, [fts_query, max_chunks_per_file, *filter_params])
        count = cursor.fetchone()[0]
        cursor.close()
        return count

    def _fetch_ranked_results(
        self,
        conn: sqlite3.Connection,
        fts_query: str,
        parsed_terms: List[str],
        max_chunks_per_file: int,
        where_clauses: List[str],
        filter_params: List[Any],
        limit: int,
        offset: int,
    ) -> List[SearchResultItem]:
        """Fetch and structure paginated search results ordered by BM25 rank."""
        additional_where = ""
        if where_clauses:
            additional_where = " AND " + " AND ".join(where_clauses)

        sql = f"""
        WITH raw_matches AS (
            SELECT chunk_id, file_id,
                   bm25(chunks_fts, 5.0, 2.0, 1.0) AS bm25_score,
                   snippet(chunks_fts, -1, '[[[HL]]]', '[[[/HL]]]', '...', 24) AS match_snippet
            FROM chunks_fts
            WHERE chunks_fts MATCH ?
        ),
        ranked AS (
            SELECT chunk_id, file_id, bm25_score, match_snippet,
                   ROW_NUMBER() OVER (
                       PARTITION BY file_id
                       ORDER BY bm25_score ASC, chunk_id ASC
                   ) AS file_rank
            FROM raw_matches
        )
        SELECT r.chunk_id, r.file_id, r.bm25_score, r.match_snippet,
               c.chunk_index, c.source_segment_index, c.content, c.token_count,
               c.page_number, c.slide_number, c.sheet_name, c.row_number,
               c.start_line, c.end_line, c.metadata_json AS chunk_meta,
               f.path AS file_path, f.filename, f.extension, f.file_type,
               f.status AS file_status, f.metadata_json AS file_meta
        FROM ranked r
        JOIN chunks c ON r.chunk_id = c.id
        JOIN files f ON r.file_id = f.id
        LEFT JOIN folders fld ON f.folder_id = fld.id
        WHERE r.file_rank <= ?
        {additional_where}
        ORDER BY r.bm25_score ASC, r.chunk_id ASC
        LIMIT ? OFFSET ?;
        """

        cursor = conn.cursor()
        cursor.execute(sql, [fts_query, max_chunks_per_file, *filter_params, limit, offset])
        rows = cursor.fetchall()
        cursor.close()

        items: List[SearchResultItem] = []
        for row in rows:
            bm25_val = float(row["bm25_score"])
            # SQLite FTS5 bm25 returns negative numbers where more negative is better rank.
            # Convert to positive normalized score for UI consumption.
            normalized_score = round(abs(bm25_val) * 1000.0, 4)

            # Format snippet and extract highlight terms
            snippet_html, highlights = SnippetFormatter.format(
                raw_snippet=row["match_snippet"],
                fallback_content=row["content"],
                terms=parsed_terms,
            )

            # Parse chunk metadata
            chunk_meta = {}
            if row["chunk_meta"]:
                try:
                    chunk_meta = json.loads(row["chunk_meta"])
                except Exception:
                    chunk_meta = {}

            file_meta = {}
            if "file_meta" in row.keys() and row["file_meta"]:
                try:
                    file_meta = json.loads(row["file_meta"])
                except Exception:
                    file_meta = {}

            ftype = row["file_type"]
            content_type = ftype if ftype in {"image", "audio", "video"} else "document"
            media_metadata = file_meta if content_type in {"image", "audio", "video"} else None

            # Failed re-indexing policy: mark stale if file status is not success
            is_stale = (row["file_status"] != "success")

            item = SearchResultItem(
                file_id=row["file_id"],
                chunk_id=row["chunk_id"],
                filename=row["filename"],
                file_path=row["file_path"],
                file_type=ftype,
                content_type=content_type,
                file_status=row["file_status"],
                is_stale=is_stale,
                chunk_index=row["chunk_index"],
                content=row["content"],
                snippet=snippet_html,
                highlights=highlights,
                page_number=row["page_number"],
                slide_number=row["slide_number"],
                sheet_name=row["sheet_name"],
                row_number=row["row_number"],
                start_line=row["start_line"],
                end_line=row["end_line"],
                score=normalized_score,
                bm25_rank=bm25_val,
                metadata=chunk_meta,
                media_metadata=media_metadata,
            )
            items.append(item)

        return items
