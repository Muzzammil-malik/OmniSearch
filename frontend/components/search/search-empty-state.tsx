"use client";

import React from "react";
import { Search, FolderPlus, Sparkles, ArrowRight } from "lucide-react";
import { Button } from "../ui/button";

interface SearchEmptyStateProps {
  hasSearched: boolean;
  query: string;
  onClearQuery: () => void;
  onOpenLibrary: () => void;
  onSelectQuery?: (query: string) => void;
}

const SUGGESTED_QUERIES = [
  "database normalization",
  "discrete mathematics",
  "project report",
  "system architecture",
  "financial forecast",
];

export function SearchEmptyState({
  hasSearched,
  query,
  onClearQuery,
  onOpenLibrary,
  onSelectQuery,
}: SearchEmptyStateProps) {
  if (hasSearched) {
    return (
      <div className="flex flex-col items-center justify-center py-16 px-4 text-center max-w-md mx-auto">
        <div className="w-11 h-11 rounded-2xl bg-slate-100 dark:bg-navy-850 border border-slate-200 dark:border-navy-750 flex items-center justify-center text-slate-400 dark:text-slate-500 mb-3.5">
          <Search className="w-5 h-5 stroke-[1.5]" />
        </div>
        <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100 mb-1">
          No matches found
        </h3>
        <p className="text-xs text-slate-500 dark:text-slate-400 mb-5 leading-relaxed">
          No documents matched &ldquo;<span className="text-slate-700 dark:text-slate-300 font-medium">{query}</span>&rdquo;. Try searching different terms, switching to Semantic mode, or indexing additional folders.
        </p>
        <div className="flex items-center gap-2.5">
          <Button variant="secondary" size="xs" onClick={onClearQuery}>
            Clear search
          </Button>
          <Button variant="outline" size="xs" onClick={onOpenLibrary}>
            <FolderPlus className="w-3.5 h-3.5 mr-1" />
            Check library
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center justify-center py-14 sm:py-16 px-4 text-center max-w-lg mx-auto">
      <div className="w-12 h-12 rounded-2xl bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center text-cyan-600 dark:text-cyan-400 mb-4 shadow-inner">
        <Sparkles className="w-6 h-6 stroke-[1.75]" />
      </div>
      <h2 className="text-xl sm:text-2xl font-bold tracking-tight text-slate-900 dark:text-white mb-2">
        One search. Your entire digital world.
      </h2>
      <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 mb-6 leading-relaxed max-w-md">
        Find anything across your local PDFs, Office documents, presentations, spreadsheets, notes, and codebases.
      </p>

      {/* Suggested Queries */}
      <div className="w-full max-w-md mb-8">
        <div className="text-[11px] font-medium text-slate-400 dark:text-slate-500 uppercase tracking-wider mb-2.5">
          Try searching for
        </div>
        <div className="flex flex-wrap items-center justify-center gap-2">
          {SUGGESTED_QUERIES.map((suggestion) => (
            <button
              key={suggestion}
              onClick={() => onSelectQuery?.(suggestion)}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs bg-white dark:bg-navy-900 border border-slate-200 dark:border-navy-800 text-slate-600 dark:text-slate-300 hover:border-cyan-500/40 hover:text-cyan-600 dark:hover:text-cyan-400 hover:bg-cyan-500/5 transition-all group select-none shadow-xs"
            >
              <Search className="w-3 h-3 text-slate-400 group-hover:text-cyan-500 transition-colors" />
              <span>{suggestion}</span>
              <ArrowRight className="w-2.5 h-2.5 text-slate-300 dark:text-slate-600 group-hover:text-cyan-500 group-hover:translate-x-0.5 transition-all" />
            </button>
          ))}
        </div>
      </div>

      {/* Subtle keyboard hint */}
      <div className="flex items-center gap-2 text-xs text-slate-400 dark:text-slate-500">
        <span>Press</span>
        <kbd className="px-1.5 py-0.5 rounded bg-slate-100 dark:bg-navy-850 border border-slate-200 dark:border-navy-750 font-mono text-[10px] text-slate-600 dark:text-slate-400">
          Ctrl+K
        </kbd>
        <span>to focus search at any time</span>
      </div>
    </div>
  );
}
