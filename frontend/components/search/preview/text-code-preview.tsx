"use client";

import React, { useMemo } from "react";
import { Code, FileText } from "lucide-react";

interface TextCodePreviewProps {
  content: string;
  fileType: string;
  isCode?: boolean;
  startLine?: number | null;
  endLine?: number | null;
}

export function TextCodePreview({
  content,
  fileType,
  isCode,
  startLine,
  endLine,
}: TextCodePreviewProps) {
  const lines = useMemo(() => {
    return (content || "").split("\n");
  }, [content]);

  const initialLine = startLine || 1;

  return (
    <div className="w-full flex flex-col rounded-lg overflow-hidden bg-[#E2E6E5] dark:bg-[#06141B] border border-[#9BA8AB]/50 dark:border-[#253745]">
      {/* Header bar */}
      <div className="px-3 py-1.5 bg-[#D8DCDB] dark:bg-[#11212D] border-b border-[#9BA8AB]/40 dark:border-[#253745] flex items-center justify-between text-[11px] font-mono text-[#4A5C6A] dark:text-[#9BA8AB]">
        <div className="flex items-center gap-1.5">
          {isCode ? <Code className="w-3.5 h-3.5" /> : <FileText className="w-3.5 h-3.5" />}
          <span className="uppercase font-semibold">{fileType}</span>
        </div>
        {startLine && (
          <span>
            {endLine ? `Lines ${startLine}–${endLine}` : `Line ${startLine}`}
          </span>
        )}
      </div>

      {/* Content area */}
      <div className="max-h-[220px] overflow-auto p-3 text-xs leading-relaxed">
        {isCode ? (
          <div className="font-mono text-[11px] whitespace-pre select-text">
            {lines.map((line, idx) => (
              <div key={idx} className="flex hover:bg-[#CCD0CF]/30 dark:hover:bg-[#253745]/30">
                <span className="w-8 shrink-0 select-none text-[#4A5C6A] dark:text-[#4A5C6A] text-right pr-3 font-mono">
                  {initialLine + idx}
                </span>
                <span className="text-[#06141B] dark:text-[#CCD0CF]">{line || " "}</span>
              </div>
            ))}
          </div>
        ) : (
          <div className="font-sans text-[12px] leading-relaxed text-[#06141B] dark:text-[#CCD0CF] whitespace-pre-wrap break-words select-text">
            {content}
          </div>
        )}
      </div>
    </div>
  );
}

