"use client";

import React, { useState } from "react";
import {
  X,
  Copy,
  Check,
  Compass,
  FileText,
  Sparkles,
  ChevronDown,
  ChevronUp,
  Folder,
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

  const typeBadge = getFileTypeBadge(item.file_type);

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
    <div className="h-full flex flex-col bg-white dark:bg-navy-900 border-l border-slate-200 dark:border-navy-800 shadow-xl overflow-hidden font-sans">
      {/* Header */}
      <div className="p-4 border-b border-slate-200 dark:border-navy-800 flex items-start justify-between gap-3 bg-slate-50/50 dark:bg-navy-950/40">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 mb-1.5 flex-wrap">
            <span
              className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded-md border ${typeBadge.color}`}
            >
              {typeBadge.label}
            </span>
            {locationSummary && (
              <span className="inline-flex items-center gap-1 text-[11px] font-medium px-2 py-0.5 rounded-md bg-slate-100 dark:bg-navy-800 text-slate-600 dark:text-slate-300 border border-slate-200 dark:border-navy-750">
                <Compass className="w-3 h-3 text-cyan-500" />
                {locationSummary}
              </span>
            )}
            {item.is_stale && (
              <span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-500 border border-amber-500/20">
                Stale Index
              </span>
            )}
          </div>
          <h3
            className="text-sm sm:text-base font-semibold text-slate-900 dark:text-slate-100 truncate"
            title={item.filename}
          >
            {item.filename}
          </h3>
          <p
            onClick={handleCopyPath}
            className="text-xs text-slate-400 dark:text-slate-500 font-mono truncate mt-0.5 cursor-pointer hover:text-cyan-600 dark:hover:text-cyan-400 transition-colors"
            title="Click to copy full path"
          >
            {item.file_path}
          </p>
        </div>

        <button
          onClick={onClose}
          className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 dark:text-slate-500 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-navy-800 transition-colors shrink-0"
          title="Close preview (Esc)"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Toolbar / Actions */}
      <div className="px-4 py-2 border-b border-slate-200 dark:border-navy-800 flex items-center justify-between gap-2 bg-slate-50/40 dark:bg-navy-900/30">
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="xs" onClick={handleCopyPath}>
            {copiedPath ? (
              <Check className="w-3.5 h-3.5 text-emerald-500 mr-1" />
            ) : (
              <Copy className="w-3.5 h-3.5 mr-1" />
            )}
            <span>{copiedPath ? "Copied" : "Copy Path"}</span>
          </Button>

          <Button variant="ghost" size="xs" onClick={handleCopySnippet}>
            {copiedSnippet ? (
              <Check className="w-3.5 h-3.5 text-emerald-500 mr-1" />
            ) : (
              <Copy className="w-3.5 h-3.5 mr-1" />
            )}
            <span>{copiedSnippet ? "Copied" : "Copy Content"}</span>
          </Button>
        </div>
      </div>

      {/* Scrollable Body */}
      <div className="flex-1 overflow-y-auto p-4 space-y-5">
        {/* Section 1: Preview Content */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <h4 className="text-xs font-semibold text-slate-700 dark:text-slate-300 flex items-center gap-1.5">
              <FileText className="w-3.5 h-3.5 text-cyan-500" />
              Preview
            </h4>
          </div>
          <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-navy-950 border border-slate-200 dark:border-navy-800 font-sans text-xs leading-relaxed text-slate-800 dark:text-slate-200 whitespace-pre-wrap break-words select-text max-h-[340px] overflow-y-auto">
            {item.content}
          </div>
        </div>

        {/* Section 2: Location (if available) */}
        {locationSummary && (
          <div>
            <h4 className="text-xs font-semibold text-slate-700 dark:text-slate-300 mb-2 flex items-center gap-1.5">
              <Compass className="w-3.5 h-3.5 text-cyan-500" />
              Location
            </h4>
            <div className="grid grid-cols-2 gap-2 text-xs">
              {item.page_number && (
                <div className="p-2.5 rounded-lg bg-slate-50 dark:bg-navy-950/60 border border-slate-200 dark:border-navy-800">
                  <span className="text-slate-400 dark:text-slate-500 block text-[10px]">Page</span>
                  <span className="font-semibold text-slate-700 dark:text-slate-200">
                    Page {item.page_number}
                  </span>
                </div>
              )}
              {item.slide_number && (
                <div className="p-2.5 rounded-lg bg-slate-50 dark:bg-navy-950/60 border border-slate-200 dark:border-navy-800">
                  <span className="text-slate-400 dark:text-slate-500 block text-[10px]">Slide</span>
                  <span className="font-semibold text-slate-700 dark:text-slate-200">
                    Slide {item.slide_number}
                  </span>
                </div>
              )}
              {item.sheet_name && (
                <div className="p-2.5 rounded-lg bg-slate-50 dark:bg-navy-950/60 border border-slate-200 dark:border-navy-800">
                  <span className="text-slate-400 dark:text-slate-500 block text-[10px]">Spreadsheet</span>
                  <span className="font-semibold text-slate-700 dark:text-slate-200">
                    {item.sheet_name} {item.row_number ? `(Row ${item.row_number})` : ""}
                  </span>
                </div>
              )}
              {item.start_line && (
                <div className="p-2.5 rounded-lg bg-slate-50 dark:bg-navy-950/60 border border-slate-200 dark:border-navy-800">
                  <span className="text-slate-400 dark:text-slate-500 block text-[10px]">Source Lines</span>
                  <span className="font-semibold text-slate-700 dark:text-slate-200 font-mono">
                    {item.end_line ? `${item.start_line}–${item.end_line}` : item.start_line}
                  </span>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Section 3: Source */}
        <div>
          <h4 className="text-xs font-semibold text-slate-700 dark:text-slate-300 mb-2 flex items-center gap-1.5">
            <Folder className="w-3.5 h-3.5 text-cyan-500" />
            Source Details
          </h4>
          <div className="p-3 rounded-xl bg-slate-50 dark:bg-navy-950/60 border border-slate-200 dark:border-navy-800 space-y-1.5 text-xs">
            <div className="flex justify-between">
              <span className="text-slate-400 dark:text-slate-500">File:</span>
              <span className="font-medium text-slate-700 dark:text-slate-200 truncate max-w-[220px]">
                {item.filename}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400 dark:text-slate-500">Type:</span>
              <span className="font-mono uppercase text-slate-700 dark:text-slate-200">
                {item.file_type}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400 dark:text-slate-500">Segment:</span>
              <span className="font-mono text-slate-700 dark:text-slate-200">
                Chunk #{item.chunk_index}
              </span>
            </div>
          </div>
        </div>

        {/* Section 4: Expandable "Why this matched" (Power User Inspection) */}
        <div className="border border-slate-200 dark:border-navy-800 rounded-xl overflow-hidden bg-slate-50/50 dark:bg-navy-950/40">
          <button
            type="button"
            onClick={() => setIsWhyMatchedOpen(!isWhyMatchedOpen)}
            className="w-full flex items-center justify-between p-3 text-xs font-medium text-slate-700 dark:text-slate-300 hover:bg-slate-100/60 dark:hover:bg-navy-850/60 transition-colors"
          >
            <span className="flex items-center gap-1.5 text-cyan-600 dark:text-cyan-400">
              <Sparkles className="w-3.5 h-3.5" />
              Why this matched
            </span>
            {isWhyMatchedOpen ? (
              <ChevronUp className="w-4 h-4 text-slate-400" />
            ) : (
              <ChevronDown className="w-4 h-4 text-slate-400" />
            )}
          </button>

          {isWhyMatchedOpen && (
            <div className="p-3 pt-0 border-t border-slate-200/60 dark:border-navy-800/60 space-y-3 mt-2 text-xs">
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div className="p-2 rounded-lg bg-white dark:bg-navy-900 border border-slate-200 dark:border-navy-800">
                  <span className="text-slate-400 text-[10px] block">Hybrid Score</span>
                  <span className="font-mono font-semibold text-cyan-600 dark:text-cyan-400">
                    {item.rrf_score > 0
                      ? `${(item.rrf_score * 100).toFixed(1)}%`
                      : (item.semantic_score || 0).toFixed(2)}
                  </span>
                </div>
                {item.keyword_rank !== null && item.keyword_rank !== undefined && (
                  <div className="p-2 rounded-lg bg-white dark:bg-navy-900 border border-slate-200 dark:border-navy-800">
                    <span className="text-slate-400 text-[10px] block">Keyword Match</span>
                    <span className="font-mono font-semibold text-slate-700 dark:text-slate-200">
                      Rank #{item.keyword_rank}
                    </span>
                  </div>
                )}
                {item.semantic_rank !== null && item.semantic_rank !== undefined && (
                  <div className="p-2 rounded-lg bg-white dark:bg-navy-900 border border-slate-200 dark:border-navy-800">
                    <span className="text-slate-400 text-[10px] block">Semantic Match</span>
                    <span className="font-mono font-semibold text-slate-700 dark:text-slate-200">
                      Rank #{item.semantic_rank}
                    </span>
                  </div>
                )}
                {item.cosine_similarity !== null && item.cosine_similarity !== undefined && (
                  <div className="p-2 rounded-lg bg-white dark:bg-navy-900 border border-slate-200 dark:border-navy-800">
                    <span className="text-slate-400 text-[10px] block">Vector Similarity</span>
                    <span className="font-mono font-semibold text-slate-700 dark:text-slate-200">
                      {item.cosine_similarity.toFixed(3)}
                    </span>
                  </div>
                )}
              </div>

              {/* Matched keyword terms */}
              {item.highlights && item.highlights.length > 0 && (
                <div>
                  <span className="text-[10px] font-medium text-slate-400 uppercase tracking-wider block mb-1.5">
                    Matching Keywords
                  </span>
                  <div className="flex flex-wrap gap-1">
                    {item.highlights.map((term, i) => (
                      <span
                        key={i}
                        className="px-2 py-0.5 rounded bg-cyan-500/10 text-cyan-600 dark:text-cyan-400 border border-cyan-500/20 text-[11px] font-mono"
                      >
                        {term}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
