"use client";

import React from "react";
import { ArrowRight } from "lucide-react";
import { Button } from "../ui/button";

interface SearchEmptyStateProps {
  hasSearched: boolean;
  query: string;
  selectedFileType?: string | null;
  onClearQuery: () => void;
  onClearFileType?: () => void;
  onOpenLibrary: () => void;
  onSelectQuery?: (query: string) => void;
}

const FORMAT_LABELS: Record<string, string> = {
  pdf: "PDF",
  docx: "DOCX",
  pptx: "PPTX",
  xlsx: "Sheets",
  code: "Code",
  md: "Markdown",
  text: "Text",
  image: "Images",
  audio: "Audio",
  video: "Video",
};

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
  selectedFileType,
  onClearQuery,
  onClearFileType,
  onOpenLibrary,
  onSelectQuery,
}: SearchEmptyStateProps) {
  if (hasSearched) {
    const activeFormatLabel = selectedFileType ? FORMAT_LABELS[selectedFileType] || selectedFileType : null;

    return (
      <div className="py-14 px-4 max-w-lg mx-auto text-center">
        <p className="text-xs font-mono uppercase tracking-widest text-[#4A5C6A] dark:text-[#9BA8AB] mb-2">
          {activeFormatLabel ? `No Matching ${activeFormatLabel}` : "No Matching Passages"}
        </p>
        <h3 className="text-xl font-serif font-normal text-[#06141B] dark:text-[#CCD0CF] mb-2">
          Nothing found for &ldquo;{query}&rdquo;
          {activeFormatLabel ? ` in ${activeFormatLabel}` : ""}
        </h3>
        <p className="text-xs sm:text-sm text-[#253745] dark:text-[#9BA8AB] mb-6 leading-relaxed">
          {activeFormatLabel
            ? `No ${activeFormatLabel.toLowerCase()} files matched this query. Try switching to "All Formats" or broadening your search terms.`
            : "Try broadening your search terms, switching between Hybrid, Keyword, and Semantic retrieval modes, or verifying that your target folders are indexed."}
        </p>
        <div className="flex flex-wrap items-center justify-center gap-2.5">
          {activeFormatLabel && onClearFileType && (
            <Button variant="secondary" size="sm" onClick={onClearFileType}>
              Switch to All Formats
            </Button>
          )}
          <Button variant="secondary" size="sm" onClick={onClearQuery}>
            Clear search
          </Button>
          <Button variant="outline" size="sm" onClick={onOpenLibrary}>
            Manage library folders
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="pt-4 pb-12 max-w-2xl mx-auto">
      {/* Suggested Queries as Pill Controls */}
      <div className="pt-2">
        <div className="text-xs font-medium text-[#4A5C6A] dark:text-[#9BA8AB] mb-3">
          Try searching for
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {SUGGESTED_QUERIES.map((suggestion) => (
            <button
              key={suggestion}
              type="button"
              onClick={() => onSelectQuery?.(suggestion)}
              className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-full text-xs font-medium bg-[#D8DCDB] dark:bg-[#06141B] border border-[#9BA8AB] dark:border-[#253745] text-[#06141B] dark:text-[#CCD0CF] hover:bg-[#06141B] hover:text-[#CCD0CF] hover:border-[#06141B] dark:hover:bg-[#CCD0CF] dark:hover:text-[#06141B] dark:hover:border-[#CCD0CF] transition-colors duration-150 group select-none"
            >
              <span>{suggestion}</span>
              <ArrowRight className="w-3 h-3 text-[#4A5C6A] dark:text-[#9BA8AB] group-hover:text-current group-hover:translate-x-0.5 transition-transform" />
            </button>
          ))}
        </div>
      </div>

      {/* Quiet Keyboard Navigation Reference */}
      <div className="mt-10 pt-6 border-t border-[#9BA8AB]/60 dark:border-[#253745] flex flex-wrap items-center gap-x-5 gap-y-2 text-xs text-[#4A5C6A] dark:text-[#9BA8AB]">
        <span>
          <kbd className="font-mono text-[11px] text-[#06141B] dark:text-[#CCD0CF]">Ctrl+K</kbd>{" "}
          Focus search
        </span>
        <span aria-hidden="true">·</span>
        <span>
          <kbd className="font-mono text-[11px] text-[#06141B] dark:text-[#CCD0CF]">↑ ↓</kbd>{" "}
          Navigate results
        </span>
        <span aria-hidden="true">·</span>
        <span>
          <kbd className="font-mono text-[11px] text-[#06141B] dark:text-[#CCD0CF]">Enter</kbd>{" "}
          Inspect document
        </span>
      </div>
    </div>
  );
}
