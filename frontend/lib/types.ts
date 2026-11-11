/**
 * TypeScript type definitions mirroring OmniSearch backend FastAPI schemas.
 */

export type SearchMode = "hybrid" | "keyword" | "semantic";

export interface SearchFilter {
  file_types?: string[];
  folder_ids?: number[];
  folder_paths?: string[];
  max_chunks_per_file?: number;
}

export interface UnifiedSearchQuery {
  query: string;
  mode?: SearchMode;
  filter?: SearchFilter | null;
  limit?: number;
  offset?: number;
  rrf_k?: number;
  candidate_multiplier?: number;
  min_similarity?: number;
}

export interface HybridSearchResultItem {
  chunk_id: number;
  file_id: number;
  filename: string;
  file_path: string;
  file_type: string;
  content_type?: "document" | "image" | "audio" | "video" | string | null;
  file_status: string;
  is_stale: boolean;
  chunk_index: number;
  content: string;
  snippet: string;
  highlights: string[];
  page_number?: number | null;
  slide_number?: number | null;
  sheet_name?: string | null;
  row_number?: number | null;
  start_line?: number | null;
  end_line?: number | null;
  metadata: Record<string, unknown>;
  media_metadata?: Record<string, unknown> | null;
  embedding_source?: "native_multimodal" | "metadata_fallback" | "text" | string | null;
  rrf_score: number;
  keyword_rank?: number | null;
  semantic_rank?: number | null;
  bm25_score?: number | null;
  cosine_similarity?: number | null;
  semantic_score?: number | null;
}

export interface UnifiedSearchResponse {
  query: string;
  requested_mode: SearchMode;
  effective_mode: string;
  total_results: number;
  results: HybridSearchResultItem[];
  limit: number;
  offset: number;
  execution_time_ms: number;
  keyword_available: boolean;
  semantic_available: boolean;
  rrf_k?: number | null;
  fallback_reason?: string | null;
}

export interface FolderResponse {
  id: number;
  path: string;
  enabled: boolean;
  created_at: string;
  updated_at: string;
  file_count: number;
  total_size_bytes: number;
  chunk_count: number;
  last_indexed_at?: string | null;
}

export interface FolderListResponse {
  folders: FolderResponse[];
  total_folders: number;
}

export interface FolderCreateRequest {
  path: string;
  enabled?: boolean;
}

export interface FolderUpdateRequest {
  enabled?: boolean;
}

export interface FolderDeleteResponse {
  success: boolean;
  folder_id: number;
  message: string;
}

export type IndexJobStatus =
  | "pending"
  | "running"
  | "completed"
  | "completed_with_errors"
  | "failed"
  | "interrupted";

export interface IndexJobResponse {
  id: number;
  status: IndexJobStatus;
  total_files: number;
  processed_files: number;
  successful_files: number;
  failed_files: number;
  skipped_files: number;
  started_at: string;
  finished_at?: string | null;
  error_message?: string | null;
}

export interface IndexTriggerRequest {
  folder_id?: number | null;
  folder_path?: string | null;
  force_reindex?: boolean;
  reconcile_deleted?: boolean;
  generate_embeddings?: boolean;
  background?: boolean;
}

export interface WatcherStatusResponse {
  enabled: boolean;
  active: boolean;
  watched_folders: string[];
  pending_events: number;
  coordinator_queue_size: number;
  processed_events: number;
  current_file?: string | null;
}

export interface IndexingStatusResponse {
  is_indexing: boolean;
  current_job?: IndexJobResponse | null;
  recent_jobs: IndexJobResponse[];
  watcher?: WatcherStatusResponse | null;
}

export interface IndexingStatsResponse {
  total_folders: number;
  total_files: number;
  successful_files: number;
  failed_files: number;
  total_chunks: number;
  embedded_chunks: number;
  unembedded_chunks: number;
  total_size_bytes: number;
}

export interface DatabaseStatus {
  status: string;
  path: string;
  wal_mode: boolean;
  total_folders: number;
  total_files: number;
  total_chunks: number;
  size_bytes?: number | null;
}

export interface VectorStoreStatus {
  status: string;
  collection_name: string;
  total_vectors: number;
  unembedded_chunks: number;
  persist_dir: string;
}

export interface EmbeddingModelStatus {
  status: string;
  model_id: string;
  dimension: number;
  device: string;
  is_loaded: boolean;
  local_weights_present: boolean;
}

export interface SystemStatusResponse {
  app_name: string;
  version: string;
  environment: string;
  status: string;
  database: DatabaseStatus;
  vector_store: VectorStoreStatus;
  embedding_model: EmbeddingModelStatus;
  timestamp: string;
}

export interface ApiErrorDetail {
  error: string;
  detail: string;
  code: string;
  status_code: number;
  details?: Record<string, unknown> | null;
  timestamp: string;
}

