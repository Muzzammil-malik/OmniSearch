"use client";

import React, { useState, useEffect, useRef } from "react";
import { Music } from "lucide-react";
import { systemApi } from "@/lib/api";
import { FallbackPreview } from "./fallback-preview";

const NON_BROWSER_AUDIO_FORMATS = new Set(["wma"]);

interface AudioPreviewProps {
  filePath: string;
  fileId?: number | null;
  filename: string;
  fileType: string;
  mediaMetadata?: Record<string, unknown> | null;
}

export function AudioPreview({ filePath, fileId, filename, fileType, mediaMetadata }: AudioPreviewProps) {
  const ext = (filename.split(".").pop() || "").toLowerCase();
  const isKnownNonBrowser = NON_BROWSER_AUDIO_FORMATS.has(ext);

  const [errorMessage, setErrorMessage] = useState<string | null>(
    isKnownNonBrowser
      ? "This media format cannot be previewed in the browser."
      : null
  );

  const src = systemApi.getFileContentUrl(filePath, fileId);
  const audioRef = useRef<HTMLAudioElement>(null);
  const currentSrcRef = useRef(src);

  useEffect(() => {
    currentSrcRef.current = src;
    setErrorMessage(
      isKnownNonBrowser
        ? "This media format cannot be previewed in the browser."
        : null
    );

    if (audioRef.current) {
      audioRef.current.load();
    }
  }, [src, isKnownNonBrowser, filePath, fileId]);

  const handleError = async () => {
    const errorSrc = src;
    if (isKnownNonBrowser) {
      setErrorMessage("This media format cannot be previewed in the browser.");
      return;
    }
    try {
      const res = await fetch(errorSrc, { method: "HEAD" });
      if (currentSrcRef.current !== errorSrc) return;

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

  const elementKey = fileId ? `audio-${fileId}` : `audio-${filePath}`;

  return (
    <div className="w-full flex flex-col p-4 rounded-lg bg-[#CCD0CF]/30 dark:bg-[#06141B]/50 border border-[#9BA8AB]/40 dark:border-[#253745]">
      {/* Audio Visual Card */}
      <div className="flex items-center gap-3 mb-3">
        <div className="w-9 h-9 rounded-full bg-[#06141B] dark:bg-[#253745] flex items-center justify-center text-[#CCD0CF] shrink-0">
          <Music className="w-4 h-4" />
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-xs font-medium text-[#06141B] dark:text-[#CCD0CF] truncate font-serif">
            {filename}
          </p>
          <div className="flex items-center gap-2 text-[10px] font-mono text-[#4A5C6A] dark:text-[#9BA8AB] mt-0.5">
            <span className="uppercase">{fileType}</span>
            {Boolean(mediaMetadata?.sample_rate) && (
              <>
                <span>·</span>
                <span>{String(mediaMetadata?.sample_rate)} Hz</span>
              </>
            )}
            {Boolean(mediaMetadata?.channels) && (
              <>
                <span>·</span>
                <span>{mediaMetadata?.channels === 1 ? "Mono" : "Stereo"}</span>
              </>
            )}
          </div>
        </div>
      </div>

      {/* Native Audio Controls */}
      <audio
        key={elementKey}
        ref={audioRef}
        src={src}
        controls
        preload="metadata"
        onError={handleError}
        className="w-full h-9 rounded outline-none"
      >
        <source src={src} />
        Your browser does not support audio playback.
      </audio>
    </div>
  );
}
