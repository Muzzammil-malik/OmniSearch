"use client";

import React, { useState, useEffect, useRef } from "react";
import { AlertTriangle, ChevronRight, Compass, HelpCircle, Sparkles } from "lucide-react";
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
  const [expandedMatchId, setExpandedMatchId] = useState<number | null>(null);

  // Keyboard navigation: Up/Down arrow through results, Enter to open preview
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
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
        const isDiagnosticsOpen = expandedMatchId === item.chunk_id;

        // Clean document location pointer
        let locationText: string | null = null;
        if (item.page_number) locationText = `Page ${item.page_number}`;
        else if (item.slide_number) locationText = `Slide ${item.slide_number}`;
        else if (item.sheet_name)
          locationText = item.row_number
            ? `Sheet: ${item.sheet_name} · Row ${item.row_number}`
            : `Sheet: ${item.sheet_name}`;
        else if (item.start_line)
          locationText = item.end_line
            ? `Lines ${item.start_line}-${item.end_line}`
            : `Line ${item.start_line}`;
        else if (item.media_metadata) {
          const m = item.media_metadata as Record<string, unknown>;
          if (m.duration_formatted) locationText = `Duration ${m.duration_formatted}`;
          else if (m.width && m.height) locationText = `${m.width}x${m.height}`;
        }

        return (
          <div
            key={`${item.chunk_id}-${index}`}
            onClick={() => {
              onSelectResult(index);
              onOpenPreview(item);
            }}
            className={cn(
              "group relative p-4 rounded-2xl border transition-all duration-150 cursor-pointer text-left select-none",
              isSelected
                ? "bg-white dark:bg-navy-900 border-cyan-500/80 shadow-md ring-1 ring-cyan-500/20"
                : "bg-white/80 dark:bg-navy-900/60 border-slate-200 dark:border-navy-800 hover:border-slate-300 dark:hover:border-navy-700 hover:bg-white dark:hover:bg-navy-900"
            )}
          >
            {/* Header: Primary File Name & Location */}
            <div className="flex items-start justify-between gap-3 mb-2">
              <div className="flex items-center gap-2 flex-wrap min-w-0">
                {/* File Type Badge */}
                <span
                  className={cn(
                    "text-[10px] font-mono font-bold px-2 py-0.5 rounded-md border shrink-0",
                    typeBadge.color
                  )}
                >
                  {typeBadge.label}
                </span>

                {/* 1. File Name */}
                <h4 className="text-sm font-semibold text-slate-900 dark:text-slate-100 truncate group-hover:text-cyan-600 dark:group-hover:text-cyan-400 transition-colors">
                  {item.filename}
                </h4>

                {/* 2. Document Location Pointer */}
                {locationText && (
                  <span className="inline-flex items-center gap-1 text-[11px] font-medium px-2 py-0.5 rounded-md bg-slate-100 dark:bg-navy-800 text-slate-600 dark:text-slate-300 border border-slate-200 dark:border-navy-750">
                    <Compass className="w-3 h-3 text-cyan-500" />
                    {locationText}
                  </span>
                )}

                {/* Stale Warning Indicator */}
                {item.is_stale && (
                  <span className="inline-flex items-center gap-1 text-[10px] font-medium px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20">
                    <AlertTriangle className="w-3 h-3" />
                    Stale Index
                  </span>
                )}
              </div>

              {/* Right chevron indicator */}
              <div className="flex items-center gap-1 text-slate-400 group-hover:text-slate-600 dark:group-hover:text-slate-300 shrink-0">
                <ChevronRight className="w-4 h-4 group-hover:translate-x-0.5 transition-transform" />
              </div>
            </div>

            {/* 3. Relevant Highlighted Snippet */}
            <div
              className="text-xs leading-relaxed text-slate-600 dark:text-slate-300 font-sans line-clamp-3 mb-2.5"
              dangerouslySetInnerHTML={{
                __html: sanitizeHighlightedSnippet(item.snippet || item.content),
              }}
            />

            {/* 4. Footer: File Path & Secondary "Why this matched?" info */}
            <div className="flex items-center justify-between gap-3 text-[11px] text-slate-400 dark:text-slate-500 pt-1 border-t border-slate-100 dark:border-navy-850">
              <span className="truncate font-mono" title={item.file_path}>
                {item.file_path}
              </span>

              {/* Subtle Match Info / Why this result? Toggle */}
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  setExpandedMatchId(isDiagnosticsOpen ? null : item.chunk_id);
                }}
                className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium text-slate-500 hover:text-cyan-600 dark:text-slate-400 dark:hover:text-cyan-400 hover:bg-slate-100 dark:hover:bg-navy-800 transition-colors shrink-0"
                title="Inspect ranking details"
              >
                <HelpCircle className="w-3 h-3" />
                <span>Why this matched?</span>
              </button>
            </div>

            {/* Secondary Ranking Diagnostics Pop-down (Power User) */}
            {isDiagnosticsOpen && (
              <div
                onClick={(e) => e.stopPropagation()}
                className="mt-3 p-3 rounded-xl bg-slate-50 dark:bg-navy-950 border border-slate-200 dark:border-navy-800 text-xs space-y-2 animate-in fade-in zoom-in-95 duration-100"
              >
                <div className="flex items-center justify-between font-medium text-slate-700 dark:text-slate-200">
                  <span className="flex items-center gap-1 text-cyan-600 dark:text-cyan-400">
                    <Sparkles className="w-3.5 h-3.5" />
                    Ranking Diagnostics
                  </span>
                  <span className="font-mono text-[10px] text-slate-400">
                    Chunk #{item.chunk_index}
                  </span>
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-[11px] font-mono">
                  {item.keyword_rank !== null && item.keyword_rank !== undefined && (
                    <div className="p-1.5 rounded bg-white dark:bg-navy-900 border border-slate-200 dark:border-navy-800">
                      <span className="text-[10px] text-slate-400 block font-sans">Keyword Rank</span>
                      <span className="font-semibold text-slate-700 dark:text-slate-200">
                        #{item.keyword_rank}
                      </span>
                    </div>
                  )}
                  {item.semantic_rank !== null && item.semantic_rank !== undefined && (
                    <div className="p-1.5 rounded bg-white dark:bg-navy-900 border border-slate-200 dark:border-navy-800">
                      <span className="text-[10px] text-slate-400 block font-sans">Semantic Rank</span>
                      <span className="font-semibold text-cyan-600 dark:text-cyan-400">
                        #{item.semantic_rank}
                      </span>
                    </div>
                  )}
                  {item.cosine_similarity !== null && item.cosine_similarity !== undefined && (
                    <div className="p-1.5 rounded bg-white dark:bg-navy-900 border border-slate-200 dark:border-navy-800">
                      <span className="text-[10px] text-slate-400 block font-sans">Similarity</span>
                      <span className="font-semibold text-slate-700 dark:text-slate-200">
                        {item.cosine_similarity.toFixed(3)}
                      </span>
                    </div>
                  )}
                  <div className="p-1.5 rounded bg-white dark:bg-navy-900 border border-slate-200 dark:border-navy-800">
                    <span className="text-[10px] text-slate-400 block font-sans">Fusion Score</span>
                    <span className="font-semibold text-slate-700 dark:text-slate-200">
                      {item.rrf_score > 0
                        ? `${(item.rrf_score * 100).toFixed(1)}%`
                        : (item.semantic_score || 0).toFixed(2)}
                    </span>
                  </div>
                  {item.embedding_source && (
                    <div className="p-1.5 rounded bg-white dark:bg-navy-900 border border-slate-200 dark:border-navy-800">
                      <span className="text-[10px] text-slate-400 block font-sans">Embedding Source</span>
                      <span className="font-semibold text-slate-700 dark:text-slate-200 truncate block">
                        {item.embedding_source}
                      </span>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
