"use client";

import React from "react";
import { Search, FolderPlus, Sparkles, Command } from "lucide-react";
import { Button } from "../ui/button";

interface SearchEmptyStateProps {
  hasSearched: boolean;
  query: string;
  onClearQuery: () => void;
  onOpenLibrary: () => void;
}

export function SearchEmptyState({
  hasSearched,
  query,
  onClearQuery,
  onOpenLibrary,
}: SearchEmptyStateProps) {
  if (hasSearched) {
    return (
      <div className="flex flex-col items-center justify-center py-20 px-4 text-center max-w-md mx-auto">
        <div className="w-12 h-12 rounded-2xl bg-slate-100 dark:bg-navy-850 border border-slate-200 dark:border-navy-750 flex items-center justify-center text-slate-400 dark:text-slate-500 mb-4">
          <Search className="w-6 h-6 stroke-[1.5]" />
        </div>
        <h3 className="text-base font-semibold text-slate-900 dark:text-slate-100 mb-1">
          No matches found
        </h3>
        <p className="text-sm text-slate-500 dark:text-slate-400 mb-6 leading-relaxed">
          No document chunks matched your query &ldquo;<span className="text-slate-700 dark:text-slate-300 font-medium">{query}</span>&rdquo;. Try adjusting keywords or switching search mode.
        </p>
        <div className="flex items-center gap-3">
          <Button variant="secondary" size="sm" onClick={onClearQuery}>
            Clear search
          </Button>
          <Button variant="outline" size="sm" onClick={onOpenLibrary}>
            <FolderPlus className="w-4 h-4 mr-1.5" />
            Check folders
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center justify-center py-24 px-4 text-center max-w-lg mx-auto">
      <div className="w-14 h-14 rounded-2xl bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center text-cyan-600 dark:text-cyan-400 mb-5 shadow-inner">
        <Sparkles className="w-7 h-7 stroke-[1.75]" />
      </div>
      <h2 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white mb-2">
        One search. Your entire digital world.
      </h2>
      <p className="text-sm text-slate-500 dark:text-slate-400 mb-8 leading-relaxed max-w-md">
        Find anything across your local PDFs, Office documents, presentations, spreadsheets, markdown notes, and source code.
      </p>

      {/* Suggested prompts / shortcuts */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 w-full text-left">
        <div className="p-3 rounded-xl bg-white dark:bg-navy-900/60 border border-slate-200 dark:border-navy-800 text-xs">
          <div className="flex items-center gap-2 text-cyan-600 dark:text-cyan-400 font-medium mb-1">
            <Command className="w-3.5 h-3.5" />
            <span>Instant Access</span>
          </div>
          <span className="text-slate-500 dark:text-slate-400">
            Press <kbd className="px-1.5 py-0.5 rounded bg-slate-100 dark:bg-navy-800 border border-slate-300 dark:border-navy-700 font-mono text-[10px]">Ctrl+K</kbd> anywhere to focus search.
          </span>
        </div>

        <div className="p-3 rounded-xl bg-white dark:bg-navy-900/60 border border-slate-200 dark:border-navy-800 text-xs">
          <div className="flex items-center gap-2 text-cyan-600 dark:text-cyan-400 font-medium mb-1">
            <Sparkles className="w-3.5 h-3.5" />
            <span>Hybrid Intelligence</span>
          </div>
          <span className="text-slate-500 dark:text-slate-400">
            Combines exact SQLite BM25 lexical precision with EmbeddingGemma 2 semantic vectors.
          </span>
        </div>
      </div>
    </div>
  );
}

