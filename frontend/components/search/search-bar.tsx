"use client";

import React, { useEffect, useRef } from "react";
import { Search, X } from "lucide-react";
import { SearchMode } from "@/lib/types";
import { cn } from "@/lib/utils";

interface SearchBarProps {
  query: string;
  onQueryChange: (query: string) => void;
  mode: SearchMode;
  onModeChange: (mode: SearchMode) => void;
  selectedFileType: string | null;
  onSelectFileType: (fileType: string | null) => void;
  isLoading: boolean;
  onSearchSubmit?: () => void;
  onClear: () => void;
}

const FILE_TYPE_OPTIONS = [
  { label: "All Formats", value: null },
  { label: "PDF", value: "pdf" },
  { label: "DOCX", value: "docx" },
  { label: "PPTX", value: "pptx" },
  { label: "Sheets", value: "xlsx" },
  { label: "Code", value: "code" },
  { label: "Markdown", value: "md" },
  { label: "Text", value: "text" },
  { label: "Images", value: "image" },
  { label: "Audio", value: "audio" },
  { label: "Video", value: "video" },
];

const SEARCH_MODES: { value: SearchMode; label: string; description: string }[] = [
  {
    value: "hybrid",
    label: "Hybrid",
    description: "Combined lexical BM25 and vector similarity ranking",
  },
  {
    value: "keyword",
    label: "Keyword",
    description: "Exact SQLite FTS5 lexical matching",
  },
  {
    value: "semantic",
    label: "Semantic",
    description: "Conceptual vector similarity retrieval",
  },
];

export function SearchBar({
  query,
  onQueryChange,
  mode,
  onModeChange,
  selectedFileType,
  onSelectFileType,
  isLoading,
  onSearchSubmit,
  onClear,
}: SearchBarProps) {
  const inputRef = useRef<HTMLInputElement>(null);

  // Global Ctrl+K / Cmd+K shortcut to focus search
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        inputRef.current?.focus();
        inputRef.current?.select();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && onSearchSubmit) {
      e.preventDefault();
      onSearchSubmit();
    } else if (e.key === "Escape") {
      onClear();
      inputRef.current?.blur();
    }
  };

  return (
    <div className="w-full space-y-3.5">
      {/* Prominent Search Field Container */}
      <div className="relative flex items-center w-full rounded-xl bg-[#E2E6E5] dark:bg-[#06141B] border border-[#9BA8AB] dark:border-[#253745] shadow-subtle hover:border-[#4A5C6A] dark:hover:border-[#4A5C6A] focus-within:border-[#06141B] dark:focus-within:border-[#9BA8AB] focus-within:ring-1 focus-within:ring-[#06141B]/20 dark:focus-within:ring-[#9BA8AB]/25 transition-all duration-150">
        {/* Left Search Icon or Restrained Loading Spinner */}
        <div className="pl-4 pr-3 text-[#4A5C6A] dark:text-[#9BA8AB] flex items-center justify-center shrink-0">
          {isLoading ? (
            <div
              className="w-4 h-4 border-[1.75px] border-[#4A5C6A]/35 border-t-[#06141B] dark:border-t-[#CCD0CF] rounded-full animate-spin"
              aria-label="Searching"
            />
          ) : (
            <Search className="w-4 h-4 stroke-[1.75]" />
          )}
        </div>

        {/* Search Input */}
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => onQueryChange(e.target.value)}
          onKeyDown={handleKeyDown}
          aria-label="Search local files and documents"
          placeholder="Search files, passages, spreadsheets, or source code..."
          className="flex-1 bg-transparent py-3.5 pr-3 text-[15px] text-[#06141B] dark:text-[#CCD0CF] placeholder:text-[#4A5C6A] dark:placeholder:text-[#4A5C6A] focus:outline-none"
        />

        {/* Right Controls: Clear + Keyboard Shortcut + Search Action Pill */}
        <div className="flex items-center gap-2 pr-3 shrink-0">
          {query && (
            <button
              type="button"
              onClick={onClear}
              className="inline-flex items-center justify-center h-7 w-7 rounded-full text-[#4A5C6A] dark:text-[#9BA8AB] hover:text-[#06141B] dark:hover:text-[#CCD0CF] hover:bg-[#06141B]/[0.07] dark:hover:bg-[#253745] transition-colors"
              title="Clear search (Esc)"
              aria-label="Clear search query"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}

          <kbd className="hidden sm:inline-flex items-center px-2 py-0.5 rounded text-[11px] font-mono text-[#4A5C6A] dark:text-[#9BA8AB] bg-[#CCD0CF] dark:bg-[#11212D] border border-[#9BA8AB] dark:border-[#253745]">
            Ctrl K
          </kbd>

          {query.trim().length > 0 && onSearchSubmit && (
            <button
              type="button"
              onClick={onSearchSubmit}
              className="px-3.5 py-1.5 rounded-full text-xs font-medium bg-[#06141B] text-[#CCD0CF] hover:bg-[#11212D] dark:bg-[#CCD0CF] dark:text-[#06141B] dark:hover:bg-[#9BA8AB] transition-colors"
            >
              Search
            </button>
          )}
        </div>
      </div>

      {/* Search Mode Controls + Format Filters Row */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-0.5">
        {/* Search Mode Controls (Pill Segmented Group) */}
        <div className="flex items-center gap-2 shrink-0">
          <span className="text-xs font-medium text-[#4A5C6A] dark:text-[#9BA8AB] select-none">
            Mode
          </span>
          <div
            role="group"
            aria-label="Search retrieval mode"
            className="inline-flex items-center bg-[#D8DCDB] dark:bg-[#06141B] p-0.5 rounded-full border border-[#9BA8AB] dark:border-[#253745]"
          >
            {SEARCH_MODES.map((m) => {
              const isActive = mode === m.value;
              return (
                <button
                  key={m.value}
                  type="button"
                  onClick={() => onModeChange(m.value)}
                  title={m.description}
                  className={cn(
                    "px-3 py-1 rounded-full text-xs font-medium transition-colors duration-150 whitespace-nowrap",
                    isActive
                      ? "bg-[#06141B] text-[#CCD0CF] dark:bg-[#CCD0CF] dark:text-[#06141B]"
                      : "text-[#253745] dark:text-[#9BA8AB] hover:text-[#06141B] dark:hover:text-[#CCD0CF]"
                  )}
                >
                  {m.label}
                </button>
              );
            })}
          </div>
        </div>

        {/* Format Filters (Compact Pill Controls) */}
        <div
          role="group"
          aria-label="Filter by file format"
          className="flex items-center gap-1.5 overflow-x-auto py-0.5 text-xs"
        >
          <span className="text-[#4A5C6A] dark:text-[#9BA8AB] mr-1 select-none font-medium whitespace-nowrap">
            Format
          </span>
          {FILE_TYPE_OPTIONS.map((item) => {
            const isSelected = selectedFileType === item.value;
            return (
              <button
                key={item.label}
                type="button"
                onClick={() => onSelectFileType(item.value)}
                className={cn(
                  "px-3 py-1 rounded-full text-xs font-medium whitespace-nowrap shrink-0 transition-colors duration-150 border",
                  isSelected
                    ? "bg-[#06141B] text-[#CCD0CF] border-[#06141B] dark:bg-[#CCD0CF] dark:text-[#06141B] dark:border-[#CCD0CF]"
                    : "bg-transparent text-[#253745] dark:text-[#9BA8AB] border-[#9BA8AB] dark:border-[#253745] hover:border-[#4A5C6A] dark:hover:border-[#4A5C6A] hover:text-[#06141B] dark:hover:text-[#CCD0CF]"
                )}
              >
                {item.label}
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
