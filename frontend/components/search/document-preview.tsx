"use client";

import React, { useState } from "react";
import {
  X,
  Copy,
  Check,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { HybridSearchResultItem } from "@/lib/types";
import { getFileTypeBadge } from "@/lib/utils";
import { Button } from "../ui/button";

interface DocumentPreviewProps {
  item: HybridSearchResultItem | null;
  onClose: () => void;
}

export function DocumentPreview({ item, onClose }: DocumentPreviewProps) {
  const [copiedSnippet, setCopiedSnippet] = useState(false);
  const [copiedPath, setCopiedPath] = useState(false);
  const [isWhyMatchedOpen, setIsWhyMatchedOpen] = useState(false);

  if (!item) return null;

  const typeInfo = getFileTypeBadge(item.file_type);

  const handleCopySnippet = () => {
    navigator.clipboard.writeText(item.content);
    setCopiedSnippet(true);
    setTimeout(() => setCopiedSnippet(false), 2000);
  };

  const handleCopyPath = () => {
    navigator.clipboard.writeText(item.file_path);
    setCopiedPath(true);
    setTimeout(() => setCopiedPath(false), 2000);
  };

  // Determine user-friendly location
  let locationSummary: string | null = null;
  if (item.page_number) locationSummary = `Page ${item.page_number}`;
  else if (item.slide_number) locationSummary = `Slide ${item.slide_number}`;
  else if (item.sheet_name)
    locationSummary = item.row_number
      ? `${item.sheet_name} · Row ${item.row_number}`
      : item.sheet_name;
  else if (item.start_line)
    locationSummary = item.end_line
      ? `Lines ${item.start_line}–${item.end_line}`
      : `Line ${item.start_line}`;

  return (
    <aside
      aria-label="Document preview workspace"
      className="h-full flex flex-col bg-[#D8DCDB] dark:bg-[#11212D] border-l border-[#9BA8AB] dark:border-[#253745] overflow-hidden font-sans"
    >
      {/* Workspace Header */}
      <div className="p-5 border-b border-[#9BA8AB] dark:border-[#253745] flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          {/* Quiet unboxed metadata line */}
          <div className="flex items-center gap-1.5 text-[11px] font-mono text-[#253745] dark:text-[#9BA8AB] mb-1.5 flex-wrap">
            <span className="uppercase tracking-wider">{typeInfo.label}</span>
            {locationSummary && (
              <>
                <span aria-hidden="true" className="text-[#4A5C6A]">
                  ·
                </span>
                <span className="font-sans">{locationSummary}</span>
              </>
            )}
            <span aria-hidden="true" className="text-[#4A5C6A]">
              ·
            </span>
            <span>Chunk #{item.chunk_index}</span>
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

          <h2
            className="text-base sm:text-lg font-serif font-medium text-[#06141B] dark:text-[#CCD0CF] truncate"
            title={item.filename}
          >
            {item.filename}
          </h2>
          <button
            type="button"
            onClick={handleCopyPath}
            className="text-left text-[11px] text-[#4A5C6A] dark:text-[#9BA8AB] hover:text-[#06141B] dark:hover:text-[#CCD0CF] font-mono truncate max-w-full mt-0.5 transition-colors block"
            title="Click to copy full file path"
          >
            {item.file_path}
          </button>
        </div>

        <button
          type="button"
          onClick={onClose}
          className="inline-flex items-center justify-center h-8 w-8 rounded-full text-[#4A5C6A] dark:text-[#9BA8AB] hover:text-[#06141B] dark:hover:text-[#CCD0CF] hover:bg-[#06141B]/[0.07] dark:hover:bg-[#253745] transition-colors shrink-0"
          title="Close preview"
          aria-label="Close document preview"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Action Bar (Pill-shaped buttons) */}
      <div className="px-5 py-2.5 border-b border-[#9BA8AB]/70 dark:border-[#253745] flex items-center justify-between gap-2 bg-[#CCD0CF]/70 dark:bg-[#06141B]/70">
        <div className="flex items-center gap-2">
          <Button variant="secondary" size="xs" onClick={handleCopyPath}>
            {copiedPath ? (
              <Check className="w-3 h-3 mr-1" />
            ) : (
              <Copy className="w-3 h-3 mr-1" />
            )}
            <span>{copiedPath ? "Path copied" : "Copy path"}</span>
          </Button>

          <Button variant="secondary" size="xs" onClick={handleCopySnippet}>
            {copiedSnippet ? (
              <Check className="w-3 h-3 mr-1" />
            ) : (
              <Copy className="w-3 h-3 mr-1" />
            )}
            <span>{copiedSnippet ? "Passage copied" : "Copy passage"}</span>
          </Button>
        </div>
      </div>

      {/* Scrollable Document Body */}
      <div className="flex-1 overflow-y-auto p-5 space-y-6">
        {/* Section 1: Extracted Content Passage */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-[11px] font-mono uppercase tracking-wider text-[#4A5C6A] dark:text-[#9BA8AB]">
              Extracted Passage
            </h3>
          </div>
          <div className="p-4 rounded-xl bg-[#E2E6E5] dark:bg-[#06141B] border border-[#9BA8AB] dark:border-[#253745] font-sans text-[13px] leading-relaxed text-[#06141B] dark:text-[#CCD0CF] whitespace-pre-wrap break-words select-text max-h-[380px] overflow-y-auto">
            {item.content}
          </div>
        </div>

        {/* Section 2: Document Metadata Definition List */}
        <div>
          <h3 className="text-[11px] font-mono uppercase tracking-wider text-[#4A5C6A] dark:text-[#9BA8AB] mb-2.5">
            Document Metadata
          </h3>
          <dl className="divide-y divide-[#9BA8AB]/60 dark:divide-[#253745] border-y border-[#9BA8AB] dark:border-[#253745] text-xs">
            <div className="py-2 flex justify-between gap-4">
              <dt className="text-[#4A5C6A] dark:text-[#9BA8AB]">Filename</dt>
              <dd className="font-medium text-[#06141B] dark:text-[#CCD0CF] truncate text-right">
                {item.filename}
              </dd>
            </div>
            <div className="py-2 flex justify-between gap-4">
              <dt className="text-[#4A5C6A] dark:text-[#9BA8AB]">Format</dt>
              <dd className="font-mono uppercase text-[#06141B] dark:text-[#CCD0CF]">
                {item.file_type}
              </dd>
            </div>
            {locationSummary && (
              <div className="py-2 flex justify-between gap-4">
                <dt className="text-[#4A5C6A] dark:text-[#9BA8AB]">Location</dt>
                <dd className="font-mono text-[#06141B] dark:text-[#CCD0CF]">
                  {locationSummary}
                </dd>
              </div>
            )}
            <div className="py-2 flex justify-between gap-4">
              <dt className="text-[#4A5C6A] dark:text-[#9BA8AB]">Segment Index</dt>
              <dd className="font-mono tabular-nums text-[#06141B] dark:text-[#CCD0CF]">
                Chunk #{item.chunk_index}
              </dd>
            </div>
          </dl>
        </div>

        {/* Section 3: Expandable Retrieval Diagnostics */}
        <div className="pt-1">
          <button
            type="button"
            onClick={() => setIsWhyMatchedOpen(!isWhyMatchedOpen)}
            className="w-full flex items-center justify-between px-3.5 py-2 rounded-full border border-[#9BA8AB] dark:border-[#253745] text-xs font-medium text-[#253745] dark:text-[#9BA8AB] hover:text-[#06141B] dark:hover:text-[#CCD0CF] hover:border-[#4A5C6A] dark:hover:border-[#4A5C6A] transition-colors"
          >
            <span>Retrieval ranking breakdown</span>
            {isWhyMatchedOpen ? (
              <ChevronUp className="w-3.5 h-3.5" />
            ) : (
              <ChevronDown className="w-3.5 h-3.5" />
            )}
          </button>

          {isWhyMatchedOpen && (
            <div className="mt-3 p-4 rounded-xl bg-[#E2E6E5] dark:bg-[#06141B] border border-[#9BA8AB] dark:border-[#253745] space-y-3 text-xs">
              <dl className="grid grid-cols-2 gap-3 font-mono tabular-nums">
                <div>
                  <dt className="text-[10px] font-sans text-[#4A5C6A] dark:text-[#9BA8AB]">
                    Hybrid Score
                  </dt>
                  <dd className="text-xs font-medium text-[#06141B] dark:text-[#CCD0CF] mt-0.5">
                    {item.rrf_score > 0
                      ? `${(item.rrf_score * 100).toFixed(1)}%`
                      : (item.semantic_score || 0).toFixed(2)}
                  </dd>
                </div>

                {item.keyword_rank !== null && item.keyword_rank !== undefined && (
                  <div>
                    <dt className="text-[10px] font-sans text-[#4A5C6A] dark:text-[#9BA8AB]">
                      Keyword Rank
                    </dt>
                    <dd className="text-xs font-medium text-[#06141B] dark:text-[#CCD0CF] mt-0.5">
                      #{item.keyword_rank}
                    </dd>
                  </div>
                )}

                {item.semantic_rank !== null && item.semantic_rank !== undefined && (
                  <div>
                    <dt className="text-[10px] font-sans text-[#4A5C6A] dark:text-[#9BA8AB]">
                      Semantic Rank
                    </dt>
                    <dd className="text-xs font-medium text-[#06141B] dark:text-[#CCD0CF] mt-0.5">
                      #{item.semantic_rank}
                    </dd>
                  </div>
                )}

                {item.cosine_similarity !== null && item.cosine_similarity !== undefined && (
                  <div>
                    <dt className="text-[10px] font-sans text-[#4A5C6A] dark:text-[#9BA8AB]">
                      Vector Similarity
                    </dt>
                    <dd className="text-xs font-medium text-[#06141B] dark:text-[#CCD0CF] mt-0.5">
                      {item.cosine_similarity.toFixed(3)}
                    </dd>
                  </div>
                )}
              </dl>

              {item.highlights && item.highlights.length > 0 && (
                <div className="pt-2 border-t border-[#9BA8AB]/60 dark:border-[#253745]">
                  <span className="text-[10px] font-mono uppercase tracking-wider text-[#4A5C6A] dark:text-[#9BA8AB] block mb-1">
                    Matched Terms
                  </span>
                  <p className="font-mono text-[11px] text-[#06141B] dark:text-[#CCD0CF]">
                    {item.highlights.join(" · ")}
                  </p>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </aside>
  );
}
