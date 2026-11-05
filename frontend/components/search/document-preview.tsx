"use client";

import React, { useState } from "react";
import {
  X,
  Copy,
  Check,
  Compass,
  FileCode,
  Sparkles,
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

  return (
    <div className="h-full flex flex-col bg-white dark:bg-navy-900 border-l border-slate-200 dark:border-navy-800 shadow-xl overflow-hidden">
      {/* Header */}
      <div className="p-4 border-b border-slate-200 dark:border-navy-800 flex items-start justify-between gap-3 bg-slate-50/50 dark:bg-navy-950/40">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 mb-1.5 flex-wrap">
            <span
              className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded-md border ${typeBadge.color}`}
            >
              {typeBadge.label}
            </span>
            <span className="text-[11px] font-mono text-slate-400 dark:text-slate-500">
              Chunk #{item.chunk_index}
            </span>
            {item.is_stale && (
              <span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-500 border border-amber-500/20">
                Stale
              </span>
            )}
          </div>
          <h3 className="text-base font-semibold text-slate-900 dark:text-slate-100 truncate" title={item.filename}>
            {item.filename}
          </h3>
          <p
            onClick={handleCopyPath}
            className="text-xs text-slate-500 dark:text-slate-400 font-mono truncate mt-0.5 cursor-pointer hover:text-cyan-500 transition-colors"
            title="Click to copy path"
          >
            {item.file_path}
          </p>
        </div>

        <button
          onClick={onClose}
          className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 dark:text-slate-500 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-navy-800 transition-colors shrink-0"
          title="Close preview (Esc)"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      {/* Toolbar / Actions */}
      <div className="px-4 py-2 border-b border-slate-200 dark:border-navy-800 flex items-center justify-between gap-2 bg-slate-50/30 dark:bg-navy-900/30">
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="xs" onClick={handleCopyPath}>
            {copiedPath ? (
              <Check className="w-3.5 h-3.5 text-emerald-500 mr-1" />
            ) : (
              <Copy className="w-3.5 h-3.5 mr-1" />
            )}
            <span>{copiedPath ? "Path Copied" : "Copy Path"}</span>
          </Button>

          <Button variant="ghost" size="xs" onClick={handleCopySnippet}>
            {copiedSnippet ? (
              <Check className="w-3.5 h-3.5 text-emerald-500 mr-1" />
            ) : (
              <Copy className="w-3.5 h-3.5 mr-1" />
            )}
            <span>{copiedSnippet ? "Text Copied" : "Copy Content"}</span>
          </Button>
        </div>
      </div>

      {/* Scrollable Body */}
      <div className="flex-1 overflow-y-auto p-4 space-y-5">
        {/* Full Content Block */}
        <div>
          <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500 mb-2 flex items-center gap-1.5">
            <FileCode className="w-3.5 h-3.5 text-cyan-500" />
            Chunk Text Content
          </h4>
          <div className="p-4 rounded-xl bg-slate-50 dark:bg-navy-950 border border-slate-200 dark:border-navy-800/80 font-mono text-xs leading-relaxed text-slate-800 dark:text-slate-200 whitespace-pre-wrap break-words select-text max-h-[380px] overflow-y-auto">
            {item.content}
          </div>
        </div>

        {/* Structural Coordinates */}
        <div>
          <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500 mb-2 flex items-center gap-1.5">
            <Compass className="w-3.5 h-3.5 text-cyan-500" />
            Document Coordinates
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
                <span className="text-slate-400 dark:text-slate-500 block text-[10px]">Sheet / Row</span>
                <span className="font-semibold text-slate-700 dark:text-slate-200">
                  {item.sheet_name} {item.row_number ? `(Row ${item.row_number})` : ""}
                </span>
              </div>
            )}
            {item.start_line && (
              <div className="p-2.5 rounded-lg bg-slate-50 dark:bg-navy-950/60 border border-slate-200 dark:border-navy-800">
                <span className="text-slate-400 dark:text-slate-500 block text-[10px]">Lines</span>
                <span className="font-semibold text-slate-700 dark:text-slate-200">
                  {item.end_line ? `${item.start_line} - ${item.end_line}` : item.start_line}
                </span>
              </div>
            )}
            <div className="p-2.5 rounded-lg bg-slate-50 dark:bg-navy-950/60 border border-slate-200 dark:border-navy-800">
              <span className="text-slate-400 dark:text-slate-500 block text-[10px]">Chunk Index</span>
              <span className="font-semibold text-slate-700 dark:text-slate-200 font-mono">
                #{item.chunk_index} (ID: {item.chunk_id})
              </span>
            </div>
            <div className="p-2.5 rounded-lg bg-slate-50 dark:bg-navy-950/60 border border-slate-200 dark:border-navy-800">
              <span className="text-slate-400 dark:text-slate-500 block text-[10px]">File ID</span>
              <span className="font-semibold text-slate-700 dark:text-slate-200 font-mono">
                #{item.file_id}
              </span>
            </div>
          </div>
        </div>

        {/* Fusion & Score Metrics */}
        <div>
          <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500 mb-2 flex items-center gap-1.5">
            <Sparkles className="w-3.5 h-3.5 text-cyan-500" />
            Ranking Diagnostics
          </h4>
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div className="p-2.5 rounded-lg bg-slate-50 dark:bg-navy-950/60 border border-slate-200 dark:border-navy-800">
              <span className="text-slate-400 dark:text-slate-500 block text-[10px]">RRF Score</span>
              <span className="font-mono font-semibold text-cyan-600 dark:text-cyan-400">
                {item.rrf_score.toFixed(6)}
              </span>
            </div>
            {item.keyword_rank !== null && item.keyword_rank !== undefined && (
              <div className="p-2.5 rounded-lg bg-slate-50 dark:bg-navy-950/60 border border-slate-200 dark:border-navy-800">
                <span className="text-slate-400 dark:text-slate-500 block text-[10px]">Keyword Rank</span>
                <span className="font-mono font-semibold text-slate-700 dark:text-slate-200">
                  #{item.keyword_rank}
                </span>
              </div>
            )}
            {item.semantic_rank !== null && item.semantic_rank !== undefined && (
              <div className="p-2.5 rounded-lg bg-slate-50 dark:bg-navy-950/60 border border-slate-200 dark:border-navy-800">
                <span className="text-slate-400 dark:text-slate-500 block text-[10px]">Semantic Rank</span>
                <span className="font-mono font-semibold text-slate-700 dark:text-slate-200">
                  #{item.semantic_rank}
                </span>
              </div>
            )}
            {item.cosine_similarity !== null && item.cosine_similarity !== undefined && (
              <div className="p-2.5 rounded-lg bg-slate-50 dark:bg-navy-950/60 border border-slate-200 dark:border-navy-800">
                <span className="text-slate-400 dark:text-slate-500 block text-[10px]">Cosine Similarity</span>
                <span className="font-mono font-semibold text-slate-700 dark:text-slate-200">
                  {item.cosine_similarity.toFixed(4)}
                </span>
              </div>
            )}
          </div>
        </div>

        {/* Highlighted match terms if any */}
        {item.highlights && item.highlights.length > 0 && (
          <div>
            <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500 mb-2">
              Matched Terms
            </h4>
            <div className="flex flex-wrap gap-1.5">
              {item.highlights.map((term, i) => (
                <span
                  key={i}
                  className="px-2 py-0.5 rounded-md bg-cyan-500/10 text-cyan-600 dark:text-cyan-400 border border-cyan-500/20 text-xs font-mono"
                >
                  {term}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
