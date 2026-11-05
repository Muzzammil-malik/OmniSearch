"use client";

import React, { useEffect, useRef } from "react";
import { Search, X, Sparkles, SlidersHorizontal, Cpu, BookOpen } from "lucide-react";
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
    <div className="w-full space-y-3">
      {/* Primary Input Container */}
      <div className="relative flex items-center w-full rounded-2xl bg-white dark:bg-navy-900 border border-slate-200 dark:border-navy-750 shadow-sm hover:border-slate-300 dark:hover:border-navy-700 focus-within:border-cyan-500 focus-within:ring-2 focus-within:ring-cyan-500/20 transition-all">
        {/* Left Search Icon or Loading Spinner */}
        <div className="pl-4 pr-2 text-slate-400 dark:text-slate-500 flex items-center justify-center">
          {isLoading ? (
            <div className="w-5 h-5 border-2 border-cyan-500/20 border-t-cyan-500 rounded-full animate-spin" />
          ) : (
            <Search className="w-5 h-5 stroke-[2]" />
          )}
        </div>

        {/* Input */}
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => onQueryChange(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Search by keywords, natural questions, or code snippets..."
          className="flex-1 bg-transparent py-3.5 pr-2 text-base text-slate-900 dark:text-slate-100 placeholder:text-slate-400 dark:placeholder:text-slate-500 focus:outline-none"
        />

        {/* Right side controls: Clear + Mode Selector + Ctrl+K */}
        <div className="flex items-center gap-2 pr-3">
          {query && (
            <button
              onClick={onClear}
              className="p-1 rounded-lg text-slate-400 hover:text-slate-600 dark:text-slate-500 dark:hover:text-slate-300 hover:bg-slate-100 dark:hover:bg-navy-800 transition-colors"
              title="Clear query (Esc)"
            >
              <X className="w-4 h-4" />
            </button>
          )}

          {/* Mode Pill Dropdown / Toggle */}
          <div className="flex items-center bg-slate-100 dark:bg-navy-850 p-1 rounded-xl border border-slate-200 dark:border-navy-750 text-xs">
            <button
              onClick={() => onModeChange("hybrid")}
              className={cn(
                "flex items-center gap-1.5 px-2.5 py-1 rounded-lg font-medium transition-all",
                mode === "hybrid"
                  ? "bg-white dark:bg-navy-750 text-cyan-600 dark:text-cyan-400 shadow-sm"
                  : "text-slate-500 hover:text-slate-800 dark:hover:text-slate-300"
              )}
              title="Hybrid: SQLite BM25 + EmbeddingGemma 2 RRF"
            >
              <Sparkles className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">Hybrid</span>
            </button>

            <button
              onClick={() => onModeChange("keyword")}
              className={cn(
                "flex items-center gap-1.5 px-2.5 py-1 rounded-lg font-medium transition-all",
                mode === "keyword"
                  ? "bg-white dark:bg-navy-750 text-cyan-600 dark:text-cyan-400 shadow-sm"
                  : "text-slate-500 hover:text-slate-800 dark:hover:text-slate-300"
              )}
              title="Keyword: SQLite FTS5 BM25 search"
            >
              <BookOpen className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">Keyword</span>
            </button>

            <button
              onClick={() => onModeChange("semantic")}
              className={cn(
                "flex items-center gap-1.5 px-2.5 py-1 rounded-lg font-medium transition-all",
                mode === "semantic"
                  ? "bg-white dark:bg-navy-750 text-cyan-600 dark:text-cyan-400 shadow-sm"
                  : "text-slate-500 hover:text-slate-800 dark:hover:text-slate-300"
              )}
              title="Semantic: EmbeddingGemma 2 vector similarity"
            >
              <Cpu className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">Semantic</span>
            </button>
          </div>

          {/* Shortcut indicator */}
          <span className="hidden lg:inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-mono font-medium text-slate-400 dark:text-slate-500 bg-slate-100 dark:bg-navy-800 border border-slate-200 dark:border-navy-700">
            Ctrl K
          </span>
        </div>
      </div>

      {/* Filter Row */}
      <div className="flex items-center gap-1.5 overflow-x-auto pb-1 scrollbar-none text-xs">
        <span className="text-slate-400 dark:text-slate-500 mr-1 flex items-center gap-1 select-none font-medium">
          <SlidersHorizontal className="w-3.5 h-3.5" />
          Filter:
        </span>
        {FILE_TYPE_OPTIONS.map((item) => {
          const isSelected = selectedFileType === item.value;
          return (
            <button
              key={item.label}
              onClick={() => onSelectFileType(item.value)}
              className={cn(
                "px-2.5 py-1 rounded-lg font-medium whitespace-nowrap transition-all border",
                isSelected
                  ? "bg-cyan-500/10 text-cyan-600 dark:text-cyan-400 border-cyan-500/30"
                  : "bg-white dark:bg-navy-900 text-slate-600 dark:text-slate-400 border-slate-200 dark:border-navy-800 hover:border-slate-300 dark:hover:border-navy-700"
              )}
            >
              {item.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}

