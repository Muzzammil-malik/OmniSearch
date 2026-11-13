"use client";

import React, { useState, useEffect, useRef } from "react";
import { Film } from "lucide-react";
import { systemApi } from "@/lib/api";
import { FallbackPreview } from "./fallback-preview";

const NON_BROWSER_VIDEO_FORMATS = new Set(["avi", "mkv", "wmv", "flv"]);

interface VideoPreviewProps {
  filePath: string;
  fileId?: number | null;
  filename: string;
  fileType: string;
  mediaMetadata?: Record<string, unknown> | null;
}

export function VideoPreview({ filePath, fileId, filename, fileType, mediaMetadata }: VideoPreviewProps) {
  const ext = (filename.split(".").pop() || "").toLowerCase();
  const isKnownNonBrowser = NON_BROWSER_VIDEO_FORMATS.has(ext);

  const [errorMessage, setErrorMessage] = useState<string | null>(
    isKnownNonBrowser
      ? "Preview unavailable because this video format or codec is not supported by the browser."
      : null
  );

  const src = systemApi.getFileContentUrl(filePath, fileId);
  const videoRef = useRef<HTMLVideoElement>(null);
  const currentSrcRef = useRef(src);

  // Synchronize error state & invoke native video element load on item switch
  useEffect(() => {
    currentSrcRef.current = src;
    setErrorMessage(
      isKnownNonBrowser
        ? "Preview unavailable because this video format or codec is not supported by the browser."
        : null
    );

    if (videoRef.current) {
      videoRef.current.load();
    }
  }, [src, isKnownNonBrowser, filePath, fileId]);

  const handleError = async () => {
    const errorSrc = src;
    if (isKnownNonBrowser) {
      setErrorMessage("Preview unavailable because this video format or codec is not supported by the browser.");
      return;
    }
    try {
      const res = await fetch(errorSrc, { method: "HEAD" });
      // Ensure the error corresponds to the current video (avoid race condition on rapid clicks)
      if (currentSrcRef.current !== errorSrc) return;

      if (res.status === 404) {
        setErrorMessage("File no longer exists.");
      } else if (res.status === 403) {
        setErrorMessage("Unable to access this file.");
      } else if (!res.ok) {
        setErrorMessage("Preview unavailable.");
      } else {
        setErrorMessage("Preview unavailable because this format/codec is not browser-supported.");
      }
    } catch {
      if (currentSrcRef.current === errorSrc) {
        setErrorMessage("Unable to access this file.");
      }
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

  const elementKey = fileId ? `video-${fileId}` : `video-${filePath}`;

  return (
    <div className="w-full flex flex-col items-center justify-center rounded-lg overflow-hidden bg-black/90 border border-[#9BA8AB]/40 dark:border-[#253745]">
      <video
        key={elementKey}
        ref={videoRef}
        src={src}
        controls
        preload="metadata"
        onError={handleError}
        className="w-full max-h-[260px] object-contain outline-none"
      >
        <source src={src} />
        Your browser or runtime does not support native video playback for this file.
      </video>

      {mediaMetadata && (
        <div className="w-full px-3 py-1.5 bg-[#06141B] border-t border-[#253745] flex items-center justify-between text-[11px] font-mono text-[#9BA8AB]">
          <div className="flex items-center gap-1.5">
            <Film className="w-3 h-3 text-[#CCD0CF]" />
            <span>
              {mediaMetadata.width && mediaMetadata.height
                ? `${mediaMetadata.width}×${mediaMetadata.height}`
                : "Video"}
            </span>
          </div>
          {typeof mediaMetadata.duration_seconds === "number" && (
            <span>{Math.round(mediaMetadata.duration_seconds)}s</span>
          )}
        </div>
      )}
    </div>
  );
}
