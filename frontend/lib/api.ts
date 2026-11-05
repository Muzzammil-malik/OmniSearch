/**
 * Centralized API client for OmniSearch FastAPI backend.
 */

import {
  FolderCreateRequest,
  FolderDeleteResponse,
  FolderListResponse,
  FolderResponse,
  FolderUpdateRequest,
  IndexJobResponse,
  IndexingStatsResponse,
  IndexingStatusResponse,
  IndexTriggerRequest,
  SystemStatusResponse,
  UnifiedSearchQuery,
  UnifiedSearchResponse,
} from "./types";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
const API_PREFIX = "/api/v1";

export class ApiError extends Error {
  statusCode: number;
  code: string;
  detail: string;
  details?: Record<string, unknown> | null;

  constructor(statusCode: number, code: string, detail: string, details?: Record<string, unknown> | null) {
    super(detail);
    this.name = "ApiError";
    this.statusCode = statusCode;
    this.code = code;
    this.detail = detail;
    this.details = details;
  }
}

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${BASE_URL}${API_PREFIX}${endpoint}`;
  const headers = new Headers(options.headers || {});
  if (!headers.has("Content-Type") && options.body && typeof options.body === "string") {
    headers.set("Content-Type", "application/json");
  }
  headers.set("Accept", "application/json");

  try {
    const response = await fetch(url, {
      ...options,
      headers,
    });

    if (!response.ok) {
      let errorData;
      try {
        errorData = await response.json();
      } catch {
        errorData = { detail: response.statusText, code: "HTTP_ERROR" };
      }

      throw new ApiError(
        response.status,
        errorData.code || "REQUEST_FAILED",
        errorData.detail || errorData.error || `Request failed with status ${response.status}`,
        errorData.details
      );
    }

    return (await response.json()) as T;
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    if (error instanceof DOMException && error.name === "AbortError") {
      throw error;
    }
    throw new ApiError(
      0,
      "NETWORK_ERROR",
      error instanceof Error ? error.message : "Unable to connect to OmniSearch backend"
    );
  }
}

// ----------------------------------------------------------------------------
// Search Service Endpoints
// ----------------------------------------------------------------------------
export const searchApi = {
  unifiedSearch: async (
    query: UnifiedSearchQuery,
    signal?: AbortSignal
  ): Promise<UnifiedSearchResponse> => {
    return request<UnifiedSearchResponse>("/search/unified", {
      method: "POST",
      body: JSON.stringify(query),
      signal,
    });
  },
};

// ----------------------------------------------------------------------------
// Folder Management Endpoints
// ----------------------------------------------------------------------------
export const folderApi = {
  list: async (signal?: AbortSignal): Promise<FolderListResponse> => {
    return request<FolderListResponse>("/folders", { signal });
  },

  create: async (data: FolderCreateRequest): Promise<FolderResponse> => {
    return request<FolderResponse>("/folders", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  update: async (folderId: number, data: FolderUpdateRequest): Promise<FolderResponse> => {
    return request<FolderResponse>(`/folders/${folderId}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    });
  },

  delete: async (folderId: number): Promise<FolderDeleteResponse> => {
    return request<FolderDeleteResponse>(`/folders/${folderId}`, {
      method: "DELETE",
    });
  },

  triggerIndex: async (folderId: number, options?: Partial<IndexTriggerRequest>): Promise<IndexJobResponse> => {
    return request<IndexJobResponse>(`/folders/${folderId}/index`, {
      method: "POST",
      body: JSON.stringify(options || {}),
    });
  },
};

// ----------------------------------------------------------------------------
// Indexing Lifecycle & Metrics Endpoints
// ----------------------------------------------------------------------------
export const indexingApi = {
  start: async (options: IndexTriggerRequest): Promise<IndexJobResponse> => {
    return request<IndexJobResponse>("/indexing/start", {
      method: "POST",
      body: JSON.stringify(options),
    });
  },

  getStatus: async (signal?: AbortSignal): Promise<IndexingStatusResponse> => {
    return request<IndexingStatusResponse>("/indexing/status", { signal });
  },

  getJobs: async (limit = 20, signal?: AbortSignal): Promise<IndexJobResponse[]> => {
    return request<IndexJobResponse[]>(`/indexing/jobs?limit=${limit}`, { signal });
  },

  getJob: async (jobId: number, signal?: AbortSignal): Promise<IndexJobResponse> => {
    return request<IndexJobResponse>(`/indexing/jobs/${jobId}`, { signal });
  },

  getStats: async (signal?: AbortSignal): Promise<IndexingStatsResponse> => {
    return request<IndexingStatsResponse>("/indexing/stats", { signal });
  },
};

// ----------------------------------------------------------------------------
// System Diagnostics & Health Endpoints
// ----------------------------------------------------------------------------
export const systemApi = {
  getStatus: async (signal?: AbortSignal): Promise<SystemStatusResponse> => {
    return request<SystemStatusResponse>("/system/status", { signal });
  },

  getStats: async (signal?: AbortSignal): Promise<Record<string, unknown>> => {
    return request<Record<string, unknown>>("/system/stats", { signal });
  },

  getHealth: async (signal?: AbortSignal): Promise<{ status: string; app: string; version: string }> => {
    return request<{ status: string; app: string; version: string }>("/health", { signal });
  },
};

