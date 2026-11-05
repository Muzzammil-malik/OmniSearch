"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import { SearchBar } from "./search-bar";
import { SearchResults } from "./search-results";
import { DocumentPreview } from "./document-preview";
import { SearchEmptyState } from "./search-empty-state";
import { SearchErrorState } from "./search-error-state";
import { searchApi } from "@/lib/api";
import {
  HybridSearchResultItem,
  SearchMode,
  UnifiedSearchResponse,
} from "@/lib/types";

interface SearchViewProps {
  onOpenLibrary: () => void;
  defaultMode?: SearchMode;
  defaultLimit?: number;
}

export function SearchView({
  onOpenLibrary,
  defaultMode = "hybrid",
  defaultLimit = 20,
}: SearchViewProps) {
  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [mode, setMode] = useState<SearchMode>(defaultMode);
  const [selectedFileType, setSelectedFileType] = useState<string | null>(null);

  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchResponse, setSearchResponse] = useState<UnifiedSearchResponse | null>(null);

  const [selectedIndex, setSelectedIndex] = useState(0);
  const [selectedItem, setSelectedItem] = useState<HybridSearchResultItem | null>(null);

  const abortControllerRef = useRef<AbortController | null>(null);

  // Debounce query typing (280ms)
  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedQuery(query.trim());
    }, 280);
    return () => clearTimeout(handler);
  }, [query]);

  // Execute search when debouncedQuery, mode, or selectedFileType changes
  const executeSearch = useCallback(
    async (searchQuery: string) => {
      if (!searchQuery) {
        setSearchResponse(null);
        setSelectedItem(null);
        setError(null);
        return;
      }

      // Cancel any ongoing fetch
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      abortControllerRef.current = new AbortController();

      setIsLoading(true);
      setError(null);

      try {
        const response = await searchApi.unifiedSearch(
          {
            query: searchQuery,
            mode,
            limit: defaultLimit,
            filter: selectedFileType ? { file_types: [selectedFileType] } : null,
          },
          abortControllerRef.current.signal
        );

        setSearchResponse(response);
        setSelectedIndex(0);
        // Pre-select first result for preview if on desktop
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
    [mode, selectedFileType, defaultLimit]
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
      {/* Top Search Controls Bar */}
      <div className="p-4 sm:p-6 border-b border-slate-200 dark:border-navy-800 bg-white/70 dark:bg-navy-900/60 backdrop-blur-md sticky top-0 z-20">
        <div className="max-w-4xl mx-auto">
          <SearchBar
            query={query}
            onQueryChange={setQuery}
            mode={mode}
            onModeChange={setMode}
            selectedFileType={selectedFileType}
            onSelectFileType={setSelectedFileType}
            isLoading={isLoading}
            onSearchSubmit={() => executeSearch(query.trim())}
            onClear={handleClear}
          />

          {/* Results Summary Bar */}
          {searchResponse && (
            <div className="mt-2.5 flex items-center justify-between text-xs text-slate-500 dark:text-slate-400">
              <div className="flex items-center gap-2">
                <span className="font-medium text-slate-700 dark:text-slate-300">
                  {searchResponse.total_results} {searchResponse.total_results === 1 ? "result" : "results"}
                </span>
                <span>·</span>
                <span>{searchResponse.execution_time_ms.toFixed(0)} ms</span>

                {/* Subtle fallback indicator if degraded */}
                {searchResponse.effective_mode === "keyword_only" && (
                  <>
                    <span>·</span>
                    <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20">
                      Keyword fallback
                    </span>
                  </>
                )}
                {searchResponse.effective_mode === "semantic_only" && (
                  <>
                    <span>·</span>
                    <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20">
                      Semantic fallback
                    </span>
                  </>
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Main Results & Preview Area */}
      <div className="flex-1 flex overflow-hidden">
        {/* Results List View */}
        <div className="flex-1 overflow-y-auto px-4 sm:px-6 py-6">
          <div className="max-w-4xl mx-auto">
            {error ? (
              <SearchErrorState error={error} onRetry={handleRetry} />
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
                onClearQuery={handleClear}
                onOpenLibrary={onOpenLibrary}
                onSelectQuery={(suggestion) => {
                  setQuery(suggestion);
                  executeSearch(suggestion);
                }}
              />
            )}
          </div>
        </div>

        {/* Document Preview Pane (Split Screen for Desktop) */}
        {selectedItem && (
          <div className="hidden lg:block w-[460px] shrink-0 h-full">
            <DocumentPreview
              item={selectedItem}
              onClose={() => setSelectedItem(null)}
            />
          </div>
        )}

        {/* Mobile/Tablet Preview Drawer / Modal */}
        {selectedItem && (
          <div className="lg:hidden fixed inset-0 z-50 bg-slate-950/70 backdrop-blur-sm flex justify-end">
            <div className="w-full max-w-md h-full bg-white dark:bg-navy-900 shadow-2xl animate-in slide-in-from-right">
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

