"use client";

import React, { useState } from "react";
import { systemApi } from "@/lib/api";
import { FallbackPreview } from "./fallback-preview";

interface PdfPreviewProps {
  filePath: string;
  fileId?: number | null;
  filename: string;
  pageNumber?: number | null;
}

export function PdfPreview({ filePath, fileId, filename, pageNumber }: PdfPreviewProps) {
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const baseSrc = systemApi.getFileContentUrl(filePath, fileId);
  // Chromium PDF viewer accepts #page=N&toolbar=0&navpanes=0
  const pageParam = pageNumber ? `page=${pageNumber}&` : "";
  const iframeSrc = `${baseSrc}#${pageParam}toolbar=0&navpanes=0`;

  const handleError = async () => {
    setIsLoading(false);
    try {
      const res = await fetch(baseSrc, { method: "HEAD" });
      if (res.status === 404) {
        setErrorMessage("File no longer exists.");
      } else if (res.status === 403) {
        setErrorMessage("Unable to access this file.");
      } else if (!res.ok) {
        setErrorMessage("Preview unavailable.");
      } else {
        setErrorMessage("PDF preview could not be loaded into embedded viewer.");
      }
    } catch {
      setErrorMessage("Unable to access this file.");
    }
  };

  if (errorMessage) {
    return (
      <FallbackPreview
        filename={filename}
        filePath={filePath}
        fileType="pdf"
        message={errorMessage}
      />
    );
  }

  return (
    <div className="relative w-full h-[260px] rounded-lg overflow-hidden bg-white border border-[#9BA8AB]/50 dark:border-[#253745]">
      {isLoading && (
        <div className="absolute inset-0 flex items-center justify-center bg-[#CCD0CF]/40 dark:bg-[#06141B]/60 text-xs text-[#4A5C6A] dark:text-[#9BA8AB] font-mono z-10">
          <div className="w-5 h-5 border-[1.75px] border-[#4A5C6A]/30 border-t-[#06141B] dark:border-t-[#CCD0CF] rounded-full animate-spin mr-2" />
          <span>Loading PDF preview...</span>
        </div>
      )}

      <iframe
        src={iframeSrc}
        title={filename}
        onLoad={() => setIsLoading(false)}
        onError={handleError}
        className="w-full h-full border-0"
      />
    </div>
  );
}

