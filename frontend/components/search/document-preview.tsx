"use client";

import React, { useState } from "react";
import {
  AlertCircle,
  Check,
  ChevronDown,
  ChevronUp,
  Copy,
  ExternalLink,
  FolderOpen,
  X,
} from "lucide-react";
import { HybridSearchResultItem } from "@/lib/types";
import { getFileTypeBadge } from "@/lib/utils";
import { openFile, revealFile } from "@/lib/native/file-actions";
import { FilePreview } from "./preview/file-preview";
import { Button } from "../ui/button";

interface DocumentPreviewProps {
  item: HybridSearchResultItem | null;
  onClose: () => void;
}

export function DocumentPreview({ item, onClose }: DocumentPreviewProps) {
  const [copiedSnippet, setCopiedSnippet] = useState(false);
  const [copiedPath, setCopiedPath] = useState(false);
  const [isWhyMatchedOpen, setIsWhyMatchedOpen] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [isOpening, setIsOpening] = useState(false);
  const [isRevealing, setIsRevealing] = useState(false);

  if (!item) return null;

  const typeInfo = getFileTypeBadge(item.file_type);

  const handleOpenFile = async () => {
    setActionError(null);
    setIsOpening(true);
    try {
      const res = await openFile(item.file_path);
      if (!res.success) {
        setActionError(res.error || "File no longer exists at this location.");
        setTimeout(() => setActionError(null), 4000);
      }
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Failed to open file.");
      setTimeout(() => setActionError(null), 4000);
    } finally {
      setIsOpening(false);
    }
  };

  const handleRevealFile = async () => {
    setActionError(null);
    setIsRevealing(true);
    try {
      const res = await revealFile(item.file_path);
      if (!res.success) {
        setActionError(res.error || "File no longer exists at this location.");
        setTimeout(() => setActionError(null), 4000);
      }
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Failed to reveal file.");
      setTimeout(() => setActionError(null), 4000);
    } finally {
      setIsRevealing(false);
    }
  };

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
      {/* Scrollable Container covering Preview + Metadata */}
      <div className="flex-1 overflow-y-auto divide-y divide-[#9BA8AB]/50 dark:divide-[#253745]">
        {/* ========================================================================= */}
        {/* 1. TOP FILE PREVIEW AREA (Prominent visual preview for Image/Video/Audio/PDF/Doc) */}
        {/* ========================================================================= */}
        <section aria-label="File preview" className="p-4 bg-[#CCD0CF]/40 dark:bg-[#06141B]/40">
          <FilePreview item={item} />
        </section>

        {/* ========================================================================= */}
        {/* 2. FILE IDENTITY & ACTIONS HEADER */}
        {/* ========================================================================= */}
        <div className="p-5">
          <div className="flex items-start justify-between gap-3 mb-3">
            <div className="min-w-0 flex-1">
              {/* Quiet unboxed metadata line */}
              <div className="flex items-center gap-1.5 text-[11px] font-mono text-[#253745] dark:text-[#9BA8AB] mb-1.5 flex-wrap">
                <span className="uppercase tracking-wider font-semibold">{typeInfo.label}</span>
                <span aria-hidden="true" className="text-[#4A5C6A]">
                  ·
                </span>
                <span>Chunk #{item.chunk_index}</span>
                {locationSummary && (
                  <>
                    <span aria-hidden="true" className="text-[#4A5C6A]">
                      ·
                    </span>
                    <span className="font-sans">{locationSummary}</span>
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
                {copiedPath ? "✓ Path copied to clipboard" : item.file_path}
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

          {/* Primary Action Buttons: Open File + Reveal in Explorer */}
          <div className="flex flex-wrap items-center gap-2 pt-1">
            <Button
              variant="primary"
              size="sm"
              onClick={handleOpenFile}
              disabled={isOpening}
              title="Open file using Windows default application"
            >
              <ExternalLink className="w-3.5 h-3.5 mr-1.5" />
              <span>{isOpening ? "Opening..." : "Open file"}</span>
            </Button>

            <Button
              variant="secondary"
              size="sm"
              onClick={handleRevealFile}
              disabled={isRevealing}
              title="Highlight and show in Windows File Explorer"
            >
              <FolderOpen className="w-3.5 h-3.5 mr-1.5 text-yellow-500 dark:text-yellow-400" />
              <span>{isRevealing ? "Locating..." : "Reveal in File Explorer"}</span>
            </Button>

            <Button
              variant="outline"
              size="sm"
              onClick={handleCopySnippet}
              title="Copy extracted passage text to clipboard"
            >
              {copiedSnippet ? (
                <Check className="w-3.5 h-3.5 mr-1.5 text-emerald-600 dark:text-emerald-400" />
              ) : (
                <Copy className="w-3.5 h-3.5 mr-1.5" />
              )}
              <span>{copiedSnippet ? "Passage copied" : "Copy passage"}</span>
            </Button>
          </div>

          {/* Inline Action Notice / Error Alert */}
          {actionError && (
            <div className="mt-2.5 p-2 rounded-lg bg-red-500/10 border border-red-500/25 flex items-center gap-2 text-xs text-red-600 dark:text-red-400">
              <AlertCircle className="w-3.5 h-3.5 shrink-0" />
              <span>{actionError}</span>
            </div>
          )}
        </div>

        {/* ========================================================================= */}
        {/* 3. EXTRACTED PASSAGE CONTENT */}
        {/* ========================================================================= */}
        <div className="p-5">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-[11px] font-mono uppercase tracking-wider text-[#4A5C6A] dark:text-[#9BA8AB]">
              Extracted Passage
            </h3>
            <button
              type="button"
              onClick={handleCopySnippet}
              className="text-[11px] font-mono text-[#4A5C6A] dark:text-[#9BA8AB] hover:text-[#06141B] dark:hover:text-[#CCD0CF] flex items-center gap-1 transition-colors"
            >
              {copiedSnippet ? (
                <>
                  <Check className="w-3 h-3 text-emerald-600 dark:text-emerald-400" />
                  <span>Copied</span>
                </>
              ) : (
                <>
                  <Copy className="w-3 h-3" />
                  <span>Copy</span>
                </>
              )}
            </button>
          </div>
          <div className="p-4 rounded-xl bg-[#E2E6E5] dark:bg-[#06141B] border border-[#9BA8AB] dark:border-[#253745] font-sans text-[13px] leading-relaxed text-[#06141B] dark:text-[#CCD0CF] whitespace-pre-wrap break-words select-text max-h-[300px] overflow-y-auto">
            {item.content}
          </div>
        </div>

        {/* ========================================================================= */}
        {/* 4. DOCUMENT METADATA */}
        {/* ========================================================================= */}
        <div className="p-5">
          <h3 className="text-[11px] font-mono uppercase tracking-wider text-[#4A5C6A] dark:text-[#9BA8AB] mb-2.5">
            Document Metadata
          </h3>
          <dl className="divide-y divide-[#9BA8AB]/40 dark:divide-[#253745] border-y border-[#9BA8AB]/40 dark:border-[#253745] text-xs">
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
            {item.media_metadata && (
              <>
                {typeof item.media_metadata.width === "number" &&
                  typeof item.media_metadata.height === "number" && (
                    <div className="py-2 flex justify-between gap-4">
                      <dt className="text-[#4A5C6A] dark:text-[#9BA8AB]">Resolution</dt>
                      <dd className="font-mono text-[#06141B] dark:text-[#CCD0CF]">
                        {item.media_metadata.width} × {item.media_metadata.height}
                      </dd>
                    </div>
                  )}
                {typeof item.media_metadata.duration_seconds === "number" && (
                  <div className="py-2 flex justify-between gap-4">
                    <dt className="text-[#4A5C6A] dark:text-[#9BA8AB]">Duration</dt>
                    <dd className="font-mono text-[#06141B] dark:text-[#CCD0CF]">
                      {Math.round(item.media_metadata.duration_seconds)}s
                    </dd>
                  </div>
                )}
                {typeof item.media_metadata.fps === "number" && (
                  <div className="py-2 flex justify-between gap-4">
                    <dt className="text-[#4A5C6A] dark:text-[#9BA8AB]">Frame Rate</dt>
                    <dd className="font-mono text-[#06141B] dark:text-[#CCD0CF]">
                      {item.media_metadata.fps} fps
                    </dd>
                  </div>
                )}
                {typeof item.media_metadata.sample_rate === "number" && (
                  <div className="py-2 flex justify-between gap-4">
                    <dt className="text-[#4A5C6A] dark:text-[#9BA8AB]">Sample Rate</dt>
                    <dd className="font-mono text-[#06141B] dark:text-[#CCD0CF]">
                      {item.media_metadata.sample_rate} Hz
                    </dd>
                  </div>
                )}
              </>
            )}
          </dl>
        </div>

        {/* ========================================================================= */}
        {/* 5. RETRIEVAL RANKING BREAKDOWN */}
        {/* ========================================================================= */}
        <div className="p-5">
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
