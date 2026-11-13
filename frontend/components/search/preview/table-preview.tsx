"use client";

import React, { useMemo } from "react";
import { Table as TableIcon } from "lucide-react";

interface TablePreviewProps {
  content: string;
  sheetName?: string | null;
  rowNumber?: number | null;
  fileType: string;
  filename?: string;
}

/**
 * Robust RFC-compliant CSV line parser handling quotes, commas within quotes,
 * escaped quotes (""), and empty cells.
 */
function parseCsvLine(line: string, delimiter = ","): string[] {
  const result: string[] = [];
  let current = "";
  let inQuotes = false;
  let quoteChar = "";

  for (let i = 0; i < line.length; i++) {
    const char = line[i];

    if ((char === '"' || char === "'") && (!inQuotes || char === quoteChar)) {
      if (inQuotes && line[i + 1] === char) {
        // Escaped quote inside quoted field ("" or '')
        current += char;
        i++;
      } else {
        inQuotes = !inQuotes;
        quoteChar = inQuotes ? char : "";
      }
    } else if (char === delimiter && !inQuotes) {
      result.push(current.trim());
      current = "";
    } else {
      current += char;
    }
  }

  result.push(current.trim());
  return result;
}

/**
 * Parse pipe-delimited tables cleanly handling both Markdown tables (| A | B |)
 * and extracted OmniSearch segment lines (A | B | C).
 */
function parsePipeLine(line: string): string[] {
  let trimmed = line.trim();
  if (trimmed.startsWith("|")) trimmed = trimmed.slice(1);
  if (trimmed.endsWith("|")) trimmed = trimmed.slice(0, -1);
  return trimmed.split("|").map((cell) => cell.trim());
}

export function TablePreview({ content, sheetName, rowNumber, fileType, filename }: TablePreviewProps) {
  const { headers, rows, totalCols, totalRows } = useMemo(() => {
    if (!content) return { headers: [], rows: [], totalCols: 0, totalRows: 0 };

    // Normalize newlines and take up to first 50 lines for responsive preview
    const rawLines = content
      .split("\r\n")
      .join("\n")
      .split("\n")
      .map((l) => l.trim())
      .filter(Boolean)
      .slice(0, 50);

    if (rawLines.length === 0) {
      return { headers: [], rows: [], totalCols: 0, totalRows: 0 };
    }

    // Delimiter sniffing: tab, pipe, semicolon, or comma
    const firstLine = rawLines[0];
    const isTab = firstLine.includes("\t");
    const isPipe = firstLine.includes("|");
    const isSemicolon = !isTab && !isPipe && (firstLine.match(/;/g) || []).length > (firstLine.match(/,/g) || []).length;
    const delimiter = isTab ? "\t" : isSemicolon ? ";" : ",";

    const parseLine = (line: string): string[] => {
      if (isPipe) {
        return parsePipeLine(line);
      }
      return parseCsvLine(line, delimiter);
    };

    const parsedRows = rawLines.map(parseLine);

    // Filter out markdown divider lines (e.g. |---|---|)
    const cleanRows = parsedRows.filter(
      (cols) => !cols.every((c) => /^[-:\s]+$/.test(c))
    );

    if (cleanRows.length === 0) {
      return { headers: [], rows: [], totalCols: 0, totalRows: 0 };
    }

    // Determine max columns across all rows to pad ragged rows
    const maxCols = Math.max(...cleanRows.map((r) => r.length), 1);
    const normalizedRows = cleanRows.map((r) => {
      const padded = [...r];
      while (padded.length < maxCols) padded.push("");
      return padded;
    });

    let headersList: string[] = [];
    let dataRows: string[][] = [];

    // If chunk is a single row and represents a data row (row_number > 1),
    // generate generic column headers so the row itself appears as data!
    if (normalizedRows.length === 1 && typeof rowNumber === "number" && rowNumber > 1) {
      headersList = Array.from({ length: maxCols }, (_, i) => `Col ${i + 1}`);
      dataRows = normalizedRows;
    } else if (normalizedRows.length === 1) {
      // Single row, row 1 or unknown: treat as header
      headersList = normalizedRows[0];
      dataRows = [];
    } else {
      // Multiple rows: first row is headers, subsequent rows are data
      headersList = normalizedRows[0];
      dataRows = normalizedRows.slice(1);
    }

    return {
      headers: headersList,
      rows: dataRows,
      totalCols: maxCols,
      totalRows: cleanRows.length,
    };
  }, [content, rowNumber]);

  return (
    <div className="w-full flex flex-col rounded-lg overflow-hidden bg-[#E2E6E5] dark:bg-[#06141B] border border-[#9BA8AB]/50 dark:border-[#253745]">
      {/* Table Header Bar */}
      <div className="px-3 py-1.5 bg-[#D8DCDB] dark:bg-[#11212D] border-b border-[#9BA8AB]/40 dark:border-[#253745] flex items-center justify-between text-[11px] font-mono text-[#4A5C6A] dark:text-[#9BA8AB]">
        <div className="flex items-center gap-1.5 truncate">
          <TableIcon className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400 shrink-0" />
          <span className="uppercase font-semibold">{fileType || "TABLE"}</span>
          {filename && <span className="truncate max-w-[150px]">· {filename}</span>}
          {sheetName && <span>· Sheet: {sheetName}</span>}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {totalCols > 0 && (
            <span className="text-[10px] text-[#708090]">
              {totalCols} col{totalCols !== 1 ? "s" : ""}
              {totalRows > 0 ? ` · ${totalRows} row${totalRows !== 1 ? "s" : ""}` : ""}
            </span>
          )}
          {typeof rowNumber === "number" && (
            <span className="font-semibold text-emerald-700 dark:text-emerald-300">
              Row {rowNumber}
            </span>
          )}
        </div>
      </div>

      {/* Structured Table Container with Sticky Header, Horizontal & Vertical Scroll */}
      <div className="max-h-[260px] overflow-x-auto overflow-y-auto select-text">
        <table className="min-w-full text-left text-[11.5px] border-collapse font-sans">
          {headers.length > 0 && (
            <thead className="bg-[#CCD0CF] dark:bg-[#11212D] text-[#06141B] dark:text-[#CCD0CF] sticky top-0 z-10 border-b border-[#9BA8AB] dark:border-[#253745] shadow-xs">
              <tr>
                {headers.map((h, i) => (
                  <th
                    key={i}
                    scope="col"
                    className="px-3 py-1.5 font-semibold whitespace-nowrap border-r border-[#9BA8AB]/30 dark:border-[#253745]/60 last:border-r-0 tracking-tight"
                  >
                    {h || `Col ${i + 1}`}
                  </th>
                ))}
              </tr>
            </thead>
          )}
          <tbody className="divide-y divide-[#9BA8AB]/30 dark:divide-[#253745]">
            {rows.length === 0 ? (
              <tr>
                <td
                  colSpan={Math.max(headers.length, 1)}
                  className="px-3 py-3 text-center text-xs italic text-[#708090] dark:text-[#9BA8AB]"
                >
                  {headers.length > 0 ? "Header row only (no additional rows in this chunk)" : "No tabular data"}
                </td>
              </tr>
            ) : (
              rows.map((row, rIdx) => (
                <tr
                  key={rIdx}
                  className="hover:bg-[#CCD0CF]/40 dark:hover:bg-[#253745]/40 transition-colors odd:bg-transparent even:bg-[#D8DCDB]/30 dark:even:bg-[#11212D]/30"
                >
                  {row.map((cell, cIdx) => (
                    <td
                      key={cIdx}
                      className="px-3 py-1.5 text-[#253745] dark:text-[#CCD0CF] whitespace-nowrap max-w-[280px] truncate border-r border-[#9BA8AB]/20 dark:border-[#253745]/40 last:border-r-0"
                      title={cell}
                    >
                      {cell !== "" ? cell : <span className="text-[#9BA8AB] dark:text-[#4A5C6A]">-</span>}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
