"use client";

import React, { useState, useEffect, useRef } from "react";
import { ChevronRight } from "lucide-react";
import { motion } from "framer-motion";
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
        document.activeElement?.tagName === "TEXTAREA" ||
        document.activeElement?.tagName === "SELECT"
      ) {
        return;
      }

      if (e.key === "ArrowDown") {
        e.preventDefault();
        const nextIdx = Math.min(results.length - 1, selectedIndex + 1);
        onSelectResult(nextIdx);
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        const prevIdx = Math.max(0, selectedIndex - 1);
        onSelectResult(prevIdx);
      } else if (e.key === "Enter" && results[selectedIndex]) {
        e.preventDefault();
        onOpenPreview(results[selectedIndex]);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [results, selectedIndex, onSelectResult, onOpenPreview]);

  return (
    <div ref={containerRef} className="space-y-3 pb-10">
      {results.map((item, index) => {
        const isSelected = selectedIndex === index;
        const typeInfo = getFileTypeBadge(item.file_type);
        const isDiagnosticsOpen = expandedMatchId === item.chunk_id;

        // Clean document location pointer
        let locationText: string | null = null;
        if (item.page_number) locationText = `Page ${item.page_number}`;
        else if (item.slide_number) locationText = `Slide ${item.slide_number}`;
        else if (item.sheet_name)
          locationText = item.row_number
            ? `Sheet ${item.sheet_name} · Row ${item.row_number}`
            : `Sheet ${item.sheet_name}`;
        else if (item.start_line)
          locationText = item.end_line
            ? `Lines ${item.start_line}–${item.end_line}`
            : `Line ${item.start_line}`;
        else if (item.media_metadata) {
          const m = item.media_metadata as Record<string, unknown>;
          if (m.duration_formatted) locationText = `Duration ${m.duration_formatted}`;
          else if (m.width && m.height) locationText = `${m.width}×${m.height}`;
        }

        const scoreDisplay =
          item.rrf_score > 0
            ? `${(item.rrf_score * 100).toFixed(1)}% relevance`
            : item.semantic_score
            ? `${(item.semantic_score * 100).toFixed(0)}% similarity`
            : null;

        return (
          <motion.article
            key={`${item.chunk_id}-${index}`}
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{
              duration: 0.18,
              delay: Math.min(index * 0.025, 0.15),
              ease: [0.16, 1, 0.3, 1],
            }}
            onClick={() => {
              onSelectResult(index);
              onOpenPreview(item);
            }}
            className={cn(
              "group relative p-5 rounded-xl border transition-colors duration-150 cursor-pointer text-left select-none",
              isSelected
                ? "bg-[#E2E6E5] dark:bg-[#253745]/80 border-[#06141B] dark:border-[#9BA8AB] shadow-subtle"
                : "bg-[#D8DCDB] dark:bg-[#06141B]/55 border-[#9BA8AB] dark:border-[#253745] hover:border-[#4A5C6A] dark:hover:border-[#4A5C6A] hover:bg-[#E2E6E5] dark:hover:bg-[#253745]/45"
            )}
          >
            {/* 1. Primary Header: Filename + Quiet Inline Metadata */}
            <div className="flex items-baseline justify-between gap-4 mb-2">
              <div className="min-w-0 flex-1">
                <div className="flex items-baseline gap-2.5 flex-wrap">
                  <h3 className="text-[15px] font-medium text-[#06141B] dark:text-[#CCD0CF] truncate group-hover:text-[#11212D] dark:group-hover:text-white transition-colors">
                    {item.filename}
                  </h3>

                  {/* Unboxed typographic metadata with subtle middot separators */}
                  <div className="flex items-center gap-1.5 text-xs text-[#253745] dark:text-[#9BA8AB] font-mono tabular-nums">
                    <span className="uppercase tracking-wider text-[11px]">
                      {typeInfo.label}
                    </span>
                    {locationText && (
                      <>
                        <span aria-hidden="true" className="text-[#4A5C6A]">
                          ·
                        </span>
                        <span className="font-sans text-[#253745] dark:text-[#9BA8AB]">
                          {locationText}
                        </span>
                      </>
                    )}
                    {item.is_stale && (
                      <>
                        <span aria-hidden="true" className="text-[#4A5C6A]">
                          ·
                        </span>
                        <span className="font-sans text-[#9c5214] dark:text-[#fcd34d]">
                          Stale index
                        </span>
                      </>
                    )}
                  </div>
                </div>
              </div>

              {/* Right Relevance & Action Indicator */}
              <div className="flex items-center gap-2 shrink-0">
                {scoreDisplay && (
                  <span className="hidden sm:inline text-[11px] font-mono tabular-nums text-[#4A5C6A] dark:text-[#9BA8AB]">
                    {scoreDisplay}
                  </span>
                )}
                <ChevronRight className="w-4 h-4 text-[#4A5C6A] dark:text-[#9BA8AB] group-hover:text-[#06141B] dark:group-hover:text-[#CCD0CF] group-hover:translate-x-0.5 transition-all" />
              </div>
            </div>

            {/* 2. Matched Content Passage */}
            <div
              className="text-[13.5px] leading-relaxed text-[#253745] dark:text-[#9BA8AB] font-sans line-clamp-3 mb-3.5 max-w-3xl"
              dangerouslySetInnerHTML={{
                __html: sanitizeHighlightedSnippet(item.snippet || item.content),
              }}
            />

            {/* 3. Secondary Footer: File Path & Pill Inspect Toggle */}
            <div className="flex items-center justify-between gap-4 pt-2.5 border-t border-[#9BA8AB]/60 dark:border-[#253745] text-xs">
              <span
                className="truncate font-mono text-[11px] text-[#4A5C6A] dark:text-[#9BA8AB]"
                title={item.file_path}
              >
                {item.file_path}
              </span>

              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  setExpandedMatchId(isDiagnosticsOpen ? null : item.chunk_id);
                }}
                className={cn(
                  "px-2.5 py-0.5 rounded-full text-[11px] font-medium transition-colors shrink-0 border",
                  isDiagnosticsOpen
                    ? "bg-[#06141B] text-[#CCD0CF] border-[#06141B] dark:bg-[#CCD0CF] dark:text-[#06141B] dark:border-[#CCD0CF]"
                    : "bg-transparent text-[#253745] dark:text-[#9BA8AB] border-[#9BA8AB] dark:border-[#4A5C6A] hover:border-[#06141B] dark:hover:border-[#CCD0CF] hover:text-[#06141B] dark:hover:text-[#CCD0CF]"
                )}
              >
                {isDiagnosticsOpen ? "Hide match details" : "Match details"}
              </button>
            </div>

            {/* 4. Expandable Ranking Diagnostics */}
            {isDiagnosticsOpen && (
              <div
                onClick={(e) => e.stopPropagation()}
                className="mt-3 pt-3 border-t border-[#9BA8AB]/60 dark:border-[#253745] text-xs"
              >
                <div className="flex flex-wrap items-center gap-x-6 gap-y-2 font-mono tabular-nums text-[11px] text-[#253745] dark:text-[#9BA8AB]">
                  <div>
                    <span className="font-sans text-[#4A5C6A] dark:text-[#9BA8AB]/70 mr-1.5">
                      Segment:
                    </span>
                    <span className="text-[#06141B] dark:text-[#CCD0CF]">
                      Chunk #{item.chunk_index}
                    </span>
                  </div>

                  {item.keyword_rank !== null && item.keyword_rank !== undefined && (
                    <div>
                      <span className="font-sans text-[#4A5C6A] dark:text-[#9BA8AB]/70 mr-1.5">
                        Keyword Rank:
                      </span>
                      <span className="text-[#06141B] dark:text-[#CCD0CF]">
                        #{item.keyword_rank}
                      </span>
                    </div>
                  )}

                  {item.semantic_rank !== null && item.semantic_rank !== undefined && (
                    <div>
                      <span className="font-sans text-[#4A5C6A] dark:text-[#9BA8AB]/70 mr-1.5">
                        Semantic Rank:
                      </span>
                      <span className="text-[#06141B] dark:text-[#CCD0CF]">
                        #{item.semantic_rank}
                      </span>
                    </div>
                  )}

                  {item.cosine_similarity !== null && item.cosine_similarity !== undefined && (
                    <div>
                      <span className="font-sans text-[#4A5C6A] dark:text-[#9BA8AB]/70 mr-1.5">
                        Cosine Similarity:
                      </span>
                      <span className="text-[#06141B] dark:text-[#CCD0CF]">
                        {item.cosine_similarity.toFixed(3)}
                      </span>
                    </div>
                  )}

                  <div>
                    <span className="font-sans text-[#4A5C6A] dark:text-[#9BA8AB]/70 mr-1.5">
                      Fusion Score:
                    </span>
                    <span className="text-[#06141B] dark:text-[#CCD0CF]">
                      {item.rrf_score > 0
                        ? `${(item.rrf_score * 100).toFixed(1)}%`
                        : (item.semantic_score || 0).toFixed(2)}
                    </span>
                  </div>

                  {item.embedding_source && (
                    <div>
                      <span className="font-sans text-[#4A5C6A] dark:text-[#9BA8AB]/70 mr-1.5">
                        Source:
                      </span>
                      <span className="text-[#06141B] dark:text-[#CCD0CF]">
                        {item.embedding_source}
                      </span>
                    </div>
                  )}
                </div>
              </div>
            )}
          </motion.article>
        );
      })}
    </div>
  );
}
