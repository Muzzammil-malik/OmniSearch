"use client";

import React, { useMemo } from "react";
import { FileText, AlignLeft } from "lucide-react";

interface DocxPreviewProps {
  filename: string;
  content: string;
  paragraphNumber?: number | null;
}

type Block =
  | { type: "heading"; text: string; level: number }
  | { type: "bullet"; text: string }
  | { type: "number"; number: string; text: string }
  | { type: "table"; rows: string[][] }
  | { type: "paragraph"; text: string };

export function DocxPreview({ filename, content, paragraphNumber }: DocxPreviewProps) {
  const blocks = useMemo(() => {
    if (!content) return [];

    const lines = content.split("\r\n").join("\n").split("\n");
    const parsedBlocks: Block[] = [];
    let currentTableRows: string[][] = [];

    const flushTable = () => {
      if (currentTableRows.length > 0) {
        parsedBlocks.push({ type: "table", rows: currentTableRows });
        currentTableRows = [];
      }
    };

    for (let i = 0; i < lines.length; i++) {
      const rawLine = lines[i];
      const trimmed = rawLine.trim();

      if (!trimmed) {
        flushTable();
        continue;
      }

      // Check if line is a table row: contains pipe "|"
      if (trimmed.includes("|")) {
        let cleanLine = trimmed;
        if (cleanLine.startsWith("|")) cleanLine = cleanLine.slice(1);
        if (cleanLine.endsWith("|")) cleanLine = cleanLine.slice(0, -1);
        const cells = cleanLine.split("|").map((c) => c.trim());
        // Skip separator rows like |---|---|
        if (!cells.every((c) => /^[-:\s]+$/.test(c))) {
          currentTableRows.push(cells);
        }
        continue;
      }

      // Non-table line encountered
      flushTable();

      // Heading detection: markdown # or short lines with title-like attributes
      if (trimmed.startsWith("#")) {
        const level = trimmed.match(/^#+/)?.[0].length || 1;
        parsedBlocks.push({
          type: "heading",
          text: trimmed.replace(/^#+\s*/, ""),
          level: Math.min(level, 3),
        });
        continue;
      }

      // Bullet list items: •, -, *, ⁃
      const bulletMatch = trimmed.match(/^[•\-\*⁃]\s+(.*)$/);
      if (bulletMatch) {
        parsedBlocks.push({
          type: "bullet",
          text: bulletMatch[1],
        });
        continue;
      }

      // Numbered list items: 1. or 1)
      const numberMatch = trimmed.match(/^(\d+[\.\)])\s+(.*)$/);
      if (numberMatch) {
        parsedBlocks.push({
          type: "number",
          number: numberMatch[1],
          text: numberMatch[2],
        });
        continue;
      }

      // Regular paragraph
      parsedBlocks.push({
        type: "paragraph",
        text: trimmed,
      });
    }

    flushTable();
    return parsedBlocks;
  }, [content]);

  return (
    <div className="w-full flex flex-col rounded-lg overflow-hidden bg-[#E2E6E5] dark:bg-[#06141B] border border-[#9BA8AB]/50 dark:border-[#253745]">
      {/* Document Header Bar */}
      <div className="px-3 py-1.5 bg-[#D8DCDB] dark:bg-[#11212D] border-b border-[#9BA8AB]/40 dark:border-[#253745] flex items-center justify-between text-[11px] font-mono text-[#4A5C6A] dark:text-[#9BA8AB]">
        <div className="flex items-center gap-1.5 truncate">
          <FileText className="w-3.5 h-3.5 text-blue-600 dark:text-blue-400 shrink-0" />
          <span className="font-semibold text-blue-700 dark:text-blue-300">DOCX</span>
          <span className="truncate max-w-[200px]" title={filename}>
            · {filename}
          </span>
        </div>
        {paragraphNumber ? (
          <span className="shrink-0">Paragraph {paragraphNumber}</span>
        ) : (
          <span className="flex items-center gap-1 text-[10px] shrink-0 text-[#708090]">
            <AlignLeft className="w-3 h-3" />
            Document
          </span>
        )}
      </div>

      {/* Document Page Canvas (Paper sheet) */}
      <div className="p-2 sm:p-2.5">
        <div className="bg-white dark:bg-[#0c1824] rounded border border-[#9BA8AB]/30 dark:border-[#253745] shadow-xs p-4 sm:p-5 max-h-[290px] overflow-y-auto select-text font-serif">
          {blocks.length === 0 ? (
            <p className="text-xs italic text-[#708090] dark:text-[#9BA8AB]">
              No text content available for this document passage.
            </p>
          ) : (
            blocks.map((block, idx) => {
              switch (block.type) {
                case "heading": {
                  if (block.level === 1) {
                    return (
                      <h3
                        key={idx}
                        className="font-sans font-bold text-sm sm:text-[15px] text-[#06141B] dark:text-white mt-3 mb-2 tracking-tight first:mt-0"
                      >
                        {block.text}
                      </h3>
                    );
                  }
                  return (
                    <h4
                      key={idx}
                      className="font-sans font-semibold text-xs sm:text-[13px] text-[#253745] dark:text-[#CCD0CF] mt-2.5 mb-1.5 tracking-tight first:mt-0"
                    >
                      {block.text}
                    </h4>
                  );
                }

                case "bullet":
                  return (
                    <div
                      key={idx}
                      className="flex items-start gap-2 mb-1.5 pl-2 font-sans text-xs leading-relaxed text-[#06141B] dark:text-[#CCD0CF]"
                    >
                      <span
                        aria-hidden="true"
                        className="text-blue-500 font-bold select-none leading-none mt-1"
                      >
                        •
                      </span>
                      <span className="break-words">{block.text}</span>
                    </div>
                  );

                case "number":
                  return (
                    <div
                      key={idx}
                      className="flex items-start gap-2 mb-1.5 pl-2 font-sans text-xs leading-relaxed text-[#06141B] dark:text-[#CCD0CF]"
                    >
                      <span className="text-[#4A5C6A] dark:text-[#9BA8AB] font-mono text-[11px] select-none shrink-0 font-medium">
                        {block.number}
                      </span>
                      <span className="break-words">{block.text}</span>
                    </div>
                  );

                case "table":
                  return (
                    <div
                      key={idx}
                      className="my-3 overflow-x-auto rounded border border-[#9BA8AB]/40 dark:border-[#253745] font-sans"
                    >
                      <table className="w-full text-left text-[11px] border-collapse">
                        <tbody>
                          {block.rows.map((row, rIdx) => (
                            <tr
                              key={rIdx}
                              className={
                                rIdx === 0
                                  ? "bg-[#E2E6E5] dark:bg-[#11212D] font-semibold text-[#06141B] dark:text-[#CCD0CF]"
                                  : "border-t border-[#9BA8AB]/20 dark:border-[#253745]/50 hover:bg-[#CCD0CF]/20 dark:hover:bg-[#253745]/20"
                              }
                            >
                              {row.map((cell, cIdx) => (
                                <td
                                  key={cIdx}
                                  className="px-2.5 py-1 text-[#253745] dark:text-[#CCD0CF] whitespace-normal break-words"
                                >
                                  {cell || "-"}
                                </td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  );

                case "paragraph":
                default:
                  return (
                    <p
                      key={idx}
                      className="text-xs sm:text-[12.5px] leading-relaxed text-[#06141B] dark:text-[#CCD0CF] mb-3 last:mb-0 break-words whitespace-pre-wrap"
                    >
                      {block.text}
                    </p>
                  );
              }
            })
          )}
        </div>
      </div>
    </div>
  );
}

