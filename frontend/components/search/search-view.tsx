"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import { SearchBar } from "./search-bar";
import { SearchResults } from "./search-results";
import { DocumentPreview } from "./document-preview";
import { SearchEmptyState } from "./search-empty-state";
import { SearchErrorState } from "./search-error-state";
import { Skeleton } from "../ui/skeleton";
import { searchApi } from "@/lib/api";
import {
  HybridSearchResultItem,
  SearchFilter,
  SearchMode,
  UnifiedSearchResponse,
} from "@/lib/types";

interface SearchViewProps {
  onOpenLibrary: () => void;
  defaultMode?: SearchMode;
  defaultLimit?: number;
  initialFolderId?: number | null;
  onSelectFolderId?: (folderId: number | null) => void;
}

export function SearchView({
  onOpenLibrary,
  defaultMode = "hybrid",
  defaultLimit = 20,
  initialFolderId,
  onSelectFolderId,
}: SearchViewProps) {
  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [mode, setMode] = useState<SearchMode>(defaultMode);
  const [selectedFileType, setSelectedFileType] = useState<string | null>(null);
  const [selectedFolderId, setSelectedFolderId] = useState<number | null>(
    initialFolderId !== undefined ? initialFolderId : null
  );

  useEffect(() => {
    if (initialFolderId !== undefined) {
      setSelectedFolderId(initialFolderId);
    }
  }, [initialFolderId]);

  const handleSelectFolderId = (folderId: number | null) => {
    setSelectedFolderId(folderId);
    if (onSelectFolderId) {
      onSelectFolderId(folderId);
    }
  };

  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchResponse, setSearchResponse] = useState<UnifiedSearchResponse | null>(null);

  const [selectedIndex, setSelectedIndex] = useState(0);
  const [selectedItem, setSelectedItem] = useState<HybridSearchResultItem | null>(null);

  const abortControllerRef = useRef<AbortController | null>(null);

  // Sync mode if user updates defaultMode in Settings
  useEffect(() => {
    setMode(defaultMode);
  }, [defaultMode]);

  // Debounce query typing (280ms)
  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedQuery(query.trim());
    }, 280);
    return () => clearTimeout(handler);
  }, [query]);

  // Execute search when debouncedQuery, mode, selectedFileType, or selectedFolderId changes
  const executeSearch = useCallback(
    async (searchQuery: string) => {
      if (!searchQuery) {
        setSearchResponse(null);
        setSelectedItem(null);
        setError(null);
        return;
      }

      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      abortControllerRef.current = new AbortController();

      setIsLoading(true);
      setError(null);

      try {
        const filterObj: SearchFilter = {};
        if (selectedFileType) {
          filterObj.file_types = [selectedFileType];
        }
        if (selectedFolderId !== null) {
          filterObj.folder_ids = [selectedFolderId];
        }

        const response = await searchApi.unifiedSearch(
          {
            query: searchQuery,
            mode,
            limit: defaultLimit,
            filter: Object.keys(filterObj).length > 0 ? filterObj : null,
            library_folder_id: selectedFolderId,
          },
          abortControllerRef.current.signal
        );

        setSearchResponse(response);
        setSelectedIndex(0);
        if (response.results.length > 0) {
          setSelectedItem(response.results[0]);
        } else {
          setSelectedItem(null);
        }
      } catch (err: unknown) {
        if (err instanceof DOMException && err.name === "AbortError") {
          return;
        }
        const message = err instanceof Error ? err.message : "Search query failed";
        setError(message);
        setSearchResponse(null);
      } finally {
        setIsLoading(false);
      }
    },
    [mode, selectedFileType, selectedFolderId, defaultLimit]
  );

  useEffect(() => {
    executeSearch(debouncedQuery);
  }, [debouncedQuery, executeSearch]);

  const handleClear = () => {
    setQuery("");
    setDebouncedQuery("");
    setSearchResponse(null);
    setSelectedItem(null);
    setError(null);
  };

  const handleRetry = () => {
    executeSearch(debouncedQuery);
  };

  const results = searchResponse?.results || [];
  const hasSearched = Boolean(debouncedQuery);

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Top Search Workspace Header */}
      <div
        className={`px-6 sm:px-10 ${
          hasSearched
            ? "py-5 border-b border-[#9BA8AB] dark:border-[#253745]"
            : "pt-10 sm:pt-14 pb-6 border-b border-[#9BA8AB]/60 dark:border-[#253745]/70"
        } bg-[#CCD0CF]/95 dark:bg-[#11212D]/95 sticky top-0 z-20 transition-all duration-200`}
      >
        <div className="max-w-4xl mx-auto">
          {/* Editorial Heading Composition (Section 10) */}
          {!hasSearched ? (
            <div className="mb-7 max-w-2xl">
              <p className="text-[11px] font-mono uppercase tracking-widest text-[#4A5C6A] dark:text-[#9BA8AB] mb-2">
                Local-First Retrieval Workspace
              </p>
              <h1
                className="text-2xl sm:text-4xl font-serif font-normal tracking-tight text-[#06141B] dark:text-[#CCD0CF] mb-2.5"
                style={{ textWrap: "balance" }}
              >
                Everything on your computer, intelligently searchable.
              </h1>
              <p className="text-xs sm:text-sm text-[#253745] dark:text-[#9BA8AB] leading-relaxed">
                Retrieve exact passages, spreadsheets, presentations, and source code across your local directories using combined lexical and semantic indexing.
              </p>
            </div>
          ) : (
            <div className="mb-3 flex items-center justify-between gap-4">
              <p className="text-[11px] font-mono uppercase tracking-widest text-[#4A5C6A] dark:text-[#9BA8AB]">
                Search Workspace
              </p>
            </div>
          )}

          {/* Prominent Search Field + Mode Controls + Format Filters */}
          <SearchBar
            query={query}
            onQueryChange={setQuery}
            mode={mode}
            onModeChange={setMode}
            selectedFileType={selectedFileType}
            onSelectFileType={setSelectedFileType}
            selectedFolderId={selectedFolderId}
            onSelectFolderId={handleSelectFolderId}
            onOpenLibrary={onOpenLibrary}
            isLoading={isLoading}
            onSearchSubmit={() => executeSearch(query.trim())}
            onClear={handleClear}
          />

          {/* Quiet Unboxed Telemetry Summary Bar */}
          {searchResponse && (
            <div className="mt-3.5 pt-2.5 border-t border-[#9BA8AB]/50 dark:border-[#253745] flex items-center justify-between text-xs text-[#253745] dark:text-[#9BA8AB] font-mono tabular-nums">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="font-medium text-[#06141B] dark:text-[#CCD0CF] font-sans">
                  {searchResponse.total_results}{" "}
                  {searchResponse.total_results === 1 ? "result" : "results"}
                </span>
                <span aria-hidden="true" className="text-[#4A5C6A]">
                  ·
                </span>
                <span>{searchResponse.execution_time_ms.toFixed(0)} ms</span>
                <span aria-hidden="true" className="text-[#4A5C6A]">
                  ·
                </span>
                <span className="font-sans capitalize">
                  {searchResponse.effective_mode.replace(/_/g, " ")} mode
                </span>

                {searchResponse.fallback_reason && (
                  <>
                    <span aria-hidden="true" className="text-[#4A5C6A]">
                      ·
                    </span>
                    <span className="font-sans text-[#9c5214] dark:text-[#fcd34d]">
                      Fallback active
                    </span>
                  </>
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Main Results & Split Document Workspace */}
      <div className="flex-1 flex overflow-hidden">
        {/* Results Column */}
        <div className="flex-1 overflow-y-auto px-6 sm:px-10 py-6">
          <div className="max-w-4xl mx-auto">
            {error ? (
              <SearchErrorState error={error} onRetry={handleRetry} />
            ) : isLoading && !searchResponse ? (
              <div className="space-y-3" aria-label="Loading search results">
                {[0, 1, 2, 3].map((i) => (
                  <div
                    key={i}
                    className="p-5 rounded-xl bg-[#D8DCDB] dark:bg-[#06141B]/60 border border-[#9BA8AB] dark:border-[#253745] space-y-3"
                  >
                    <div className="flex items-center justify-between">
                      <Skeleton className="h-4 w-48" />
                      <Skeleton className="h-3 w-16" />
                    </div>
                    <Skeleton className="h-3.5 w-full" />
                    <Skeleton className="h-3.5 w-4/5" />
                    <Skeleton className="h-3 w-64" />
                  </div>
                ))}
              </div>
            ) : results.length > 0 ? (
              <SearchResults
                results={results}
                selectedIndex={selectedIndex}
                onSelectResult={(idx) => {
                  setSelectedIndex(idx);
                  setSelectedItem(results[idx]);
                }}
                onOpenPreview={(item) => setSelectedItem(item)}
              />
            ) : (
              <SearchEmptyState
                hasSearched={hasSearched}
                query={debouncedQuery}
                selectedFileType={selectedFileType}
                onClearQuery={handleClear}
                onClearFileType={() => setSelectedFileType(null)}
                onOpenLibrary={onOpenLibrary}
                onSelectQuery={(suggestion) => {
                  setQuery(suggestion);
                  executeSearch(suggestion);
                }}
              />
            )}
          </div>
        </div>

        {/* Desktop Document Preview Workspace */}
        {selectedItem && (
          <div className="hidden lg:block w-[440px] xl:w-[480px] shrink-0 h-full">
            <DocumentPreview
              item={selectedItem}
              onClose={() => setSelectedItem(null)}
            />
          </div>
        )}

        {/* Mobile/Tablet Preview Drawer */}
        {selectedItem && (
          <div className="lg:hidden fixed inset-0 z-50 bg-[#06141B]/65 backdrop-blur-[2px] flex justify-end">
            <div className="w-full max-w-md h-full bg-[#D8DCDB] dark:bg-[#11212D] shadow-modal">
              <DocumentPreview
                item={selectedItem}
                onClose={() => setSelectedItem(null)}
              />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
