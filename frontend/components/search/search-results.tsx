"use client";

import React, { useEffect, useRef } from "react";
import { AlertTriangle, ChevronRight, Compass } from "lucide-react";
import { HybridSearchResultItem } from "@/lib/types";
import { cn, getFileTypeBadge, sanitizeHighlightedSnippet } from "@/lib/utils";

interface SearchResultsProps {
  results: HybridSearchResultItem[];
  selectedIndex: number;
  onSelectResult: (index: number) => void;
  onOpenPreview: (item: HybridSearchResultItem) => void;
}

export function SearchResults({
  results,
  selectedIndex,
  onSelectResult,
  onOpenPreview,
}: SearchResultsProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  // Keyboard navigation: Up/Down arrow through results, Enter to open preview
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Don't intercept if user is typing in an input
      if (
        document.activeElement?.tagName === "INPUT" ||
        document.activeElement?.tagName === "TEXTAREA"
      ) {
        return;
      }

      if (e.key === "ArrowDown") {
        e.preventDefault();
        onSelectResult(Math.min(results.length - 1, selectedIndex + 1));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        onSelectResult(Math.max(0, selectedIndex - 1));
      } else if (e.key === "Enter" && results[selectedIndex]) {
        e.preventDefault();
        onOpenPreview(results[selectedIndex]);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [results, selectedIndex, onSelectResult, onOpenPreview]);

  return (
    <div ref={containerRef} className="space-y-2.5 pb-8">
      {results.map((item, index) => {
        const isSelected = selectedIndex === index;
        const typeBadge = getFileTypeBadge(item.file_type);

        // Coordinate text
        let locationText: string | null = null;
        if (item.page_number) locationText = `Page ${item.page_number}`;
        else if (item.slide_number) locationText = `Slide ${item.slide_number}`;
        else if (item.sheet_name)
          locationText = item.row_number
            ? `Sheet: ${item.sheet_name} • Row ${item.row_number}`
            : `Sheet: ${item.sheet_name}`;
        else if (item.start_line)
          locationText = item.end_line
            ? `Lines ${item.start_line}-${item.end_line}`
            : `Line ${item.start_line}`;

        return (
          <div
            key={`${item.chunk_id}-${index}`}
            onClick={() => {
              onSelectResult(index);
              onOpenPreview(item);
            }}
            className={cn(
              "group relative p-4 rounded-2xl border transition-all cursor-pointer text-left select-none",
              isSelected
                ? "bg-white dark:bg-navy-900 border-cyan-500/80 shadow-md ring-1 ring-cyan-500/20"
                : "bg-white/80 dark:bg-navy-900/60 border-slate-200 dark:border-navy-800 hover:border-slate-300 dark:hover:border-navy-700 hover:bg-white dark:hover:bg-navy-900"
            )}
          >
            {/* Header: Badges, Filename & Path */}
            <div className="flex items-start justify-between gap-3 mb-2">
              <div className="flex items-center gap-2 flex-wrap min-w-0">
                {/* File Type Badge */}
                <span
                  className={cn(
                    "text-[10px] font-mono font-bold px-2 py-0.5 rounded-md border",
                    typeBadge.color
                  )}
                >
                  {typeBadge.label}
                </span>

                {/* Filename */}
                <h4 className="text-sm font-semibold text-slate-900 dark:text-slate-100 truncate group-hover:text-cyan-600 dark:group-hover:text-cyan-400 transition-colors">
                  {item.filename}
                </h4>

                {/* Coordinate badge if present */}
                {locationText && (
                  <span className="inline-flex items-center gap-1 text-[11px] font-mono px-2 py-0.5 rounded bg-slate-100 dark:bg-navy-800 text-slate-600 dark:text-slate-400 border border-slate-200 dark:border-navy-750">
                    <Compass className="w-3 h-3 text-cyan-500" />
                    {locationText}
                  </span>
                )}

                {/* Stale Badge */}
                {item.is_stale && (
                  <span className="inline-flex items-center gap-1 text-[10px] font-medium px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20">
                    <AlertTriangle className="w-3 h-3" />
                    Stale Index
                  </span>
                )}
              </div>

              {/* RRF Rank / Relevance */}
              <div className="flex items-center gap-1.5 shrink-0">
                {item.keyword_rank && (
                  <span
                    className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-100 dark:bg-navy-800 text-slate-500 dark:text-slate-400"
                    title={`Keyword Rank #${item.keyword_rank}`}
                  >
                    Lex #{item.keyword_rank}
                  </span>
                )}
                {item.semantic_rank && (
                  <span
                    className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-cyan-500/10 text-cyan-600 dark:text-cyan-400"
                    title={`Semantic Rank #${item.semantic_rank}`}
                  >
                    Sem #{item.semantic_rank}
                  </span>
                )}
                <span className="text-[10px] font-mono font-semibold px-2 py-0.5 rounded-full bg-slate-100 dark:bg-navy-800 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-navy-700">
                  {item.rrf_score > 0
                    ? `RRF ${(item.rrf_score * 100).toFixed(1)}%`
                    : `Score ${(item.semantic_score || 0).toFixed(2)}`}
                </span>
                <ChevronRight className="w-4 h-4 text-slate-400 group-hover:translate-x-0.5 transition-transform" />
              </div>
            </div>

            {/* Snippet with safely sanitized <mark> tags */}
            <div
              className="text-xs leading-relaxed text-slate-600 dark:text-slate-300 font-sans line-clamp-3 mb-2"
              dangerouslySetInnerHTML={{
                __html: sanitizeHighlightedSnippet(item.snippet || item.content),
              }}
            />

            {/* Path info footer */}
            <div className="flex items-center gap-2 text-[11px] text-slate-400 dark:text-slate-500 truncate font-mono">
              <span className="truncate">{item.file_path}</span>
              <span className="shrink-0">•</span>
              <span className="shrink-0">Chunk #{item.chunk_index}</span>
            </div>
          </div>
        );
      })}
    </div>
  );
}
