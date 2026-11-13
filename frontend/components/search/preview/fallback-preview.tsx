"use client";

import React from "react";
import { FileQuestion, ExternalLink } from "lucide-react";
import { openFile } from "@/lib/native/file-actions";

interface FallbackPreviewProps {
  filename: string;
  filePath: string;
  fileType: string;
  message?: string;
}

export function FallbackPreview({
  filename,
  filePath,
  fileType,
  message = "This file type cannot be previewed directly in OmniSearch.",
}: FallbackPreviewProps) {
  return (
    <div className="w-full h-full min-h-[190px] flex flex-col items-center justify-center p-6 text-center rounded-lg bg-[#CCD0CF]/30 dark:bg-[#06141B]/40 border border-[#9BA8AB]/40 dark:border-[#253745]">
      <div className="w-10 h-10 rounded-full bg-[#9BA8AB]/20 dark:bg-[#253745]/60 flex items-center justify-center mb-2.5 text-[#4A5C6A] dark:text-[#9BA8AB]">
        <FileQuestion className="w-5 h-5 stroke-[1.75]" />
      </div>

      <p className="text-xs font-mono uppercase tracking-widest text-[#4A5C6A] dark:text-[#9BA8AB] mb-0.5">
        {fileType.toUpperCase()} Preview Unavailable
      </p>
      {filename && (
        <p className="text-xs font-mono font-medium text-[#06141B] dark:text-[#CCD0CF] truncate max-w-xs mb-1">
          {filename}
        </p>
      )}

      <p className="text-xs text-[#253745] dark:text-[#9BA8AB] max-w-xs mb-3.5 leading-relaxed">
        {message}
      </p>

      <button
        type="button"
        onClick={() => openFile(filePath)}
        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium bg-[#06141B] text-[#CCD0CF] hover:bg-[#11212D] dark:bg-[#CCD0CF] dark:text-[#06141B] dark:hover:bg-[#9BA8AB] transition-colors"
      >
        <ExternalLink className="w-3.5 h-3.5" />
        <span>Open file in default app</span>
      </button>
    </div>
  );
}
