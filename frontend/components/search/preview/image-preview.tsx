"use client";

import React, { useState } from "react";
import { systemApi } from "@/lib/api";
import { FallbackPreview } from "./fallback-preview";

interface ImagePreviewProps {
  filePath: string;
  fileId?: number | null;
  filename: string;
  fileType: string;
}

export function ImagePreview({ filePath, fileId, filename, fileType }: ImagePreviewProps) {
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const src = systemApi.getFileContentUrl(filePath, fileId);

  const handleError = async () => {
    setIsLoading(false);
    try {
      const res = await fetch(src, { method: "HEAD" });
      if (res.status === 404) {
        setErrorMessage("File no longer exists.");
      } else if (res.status === 403) {
        setErrorMessage("Unable to access this file.");
      } else if (!res.ok) {
        setErrorMessage("Preview unavailable.");
      } else {
        setErrorMessage("This media format cannot be previewed in the browser.");
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
        fileType={fileType}
        message={errorMessage}
      />
    );
  }

  return (
    <div className="relative w-full h-full min-h-[190px] max-h-[280px] flex items-center justify-center rounded-lg overflow-hidden bg-[#CCD0CF]/30 dark:bg-[#06141B]/40 border border-[#9BA8AB]/40 dark:border-[#253745]">
      {isLoading && (
        <div className="absolute inset-0 flex items-center justify-center text-xs text-[#4A5C6A] dark:text-[#9BA8AB] font-mono">
          <div className="w-5 h-5 border-[1.75px] border-[#4A5C6A]/30 border-t-[#06141B] dark:border-t-[#CCD0CF] rounded-full animate-spin mr-2" />
          <span>Loading image...</span>
        </div>
      )}

      {/* Standard HTML <img> tag for maximum compatibility with local file streaming and caching */}
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={src}
        alt={filename}
        onLoad={() => setIsLoading(false)}
        onError={handleError}
        className={`max-w-full max-h-[280px] w-auto h-auto object-contain transition-opacity duration-200 ${
          isLoading ? "opacity-0" : "opacity-100"
        }`}
      />
    </div>
  );
}

