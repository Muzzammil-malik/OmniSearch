import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

export function formatBytes(bytes: number, decimals = 1): string {
  if (!bytes || bytes <= 0) return "0 B";
  const k = 1024;
  const dm = decimals < 0 ? 0 : decimals;
  const sizes = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  const idx = Math.min(i, sizes.length - 1);
  return `${parseFloat((bytes / Math.pow(k, idx)).toFixed(dm))} ${sizes[idx]}`;
}

export function formatNumber(num: number): string {
  if (num === null || num === undefined) return "0";
  return new Intl.NumberFormat().format(num);
}

export function formatRelativeTime(dateString?: string | null): string {
  if (!dateString) return "Never";
  try {
    const date = new Date(dateString);
    if (isNaN(date.getTime())) return dateString;
    const now = new Date();
    const diffSeconds = Math.floor((now.getTime() - date.getTime()) / 1000);

    if (diffSeconds < 5) return "Just now";
    if (diffSeconds < 60) return `${diffSeconds}s ago`;
    const diffMinutes = Math.floor(diffSeconds / 60);
    if (diffMinutes < 60) return `${diffMinutes}m ago`;
    const diffHours = Math.floor(diffMinutes / 60);
    if (diffHours < 24) return `${diffHours}h ago`;
    const diffDays = Math.floor(diffHours / 24);
    if (diffDays < 7) return `${diffDays}d ago`;

    return date.toLocaleDateString(undefined, {
      month: "short",
      day: "numeric",
      year: date.getFullYear() !== now.getFullYear() ? "numeric" : undefined,
    });
  } catch {
    return dateString;
  }
}

/**
 * Safely escape raw text and preserve only valid <mark>...</mark> tags from the backend.
 */
export function sanitizeHighlightedSnippet(html: string): string {
  if (!html) return "";
  const parts = html.split(/(<\/?mark>)/i);
  return parts
    .map((part) => {
      if (part.toLowerCase() === "<mark>") return "<mark>";
      if (part.toLowerCase() === "</mark>") return "</mark>";
      return part
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
    })
    .join("");
}

/**
 * Restrained file type classification using the #06141B–#CCD0CF palette.
 */
export function getFileTypeBadge(fileType: string): { label: string; color: string } {
  const norm = fileType?.toLowerCase() || "unknown";
  const baseStyle =
    "bg-[#9BA8AB]/30 text-[#06141B] border-[#4A5C6A]/40 dark:bg-[#253745] dark:text-[#CCD0CF] dark:border-[#4A5C6A]";
  const accentStyle =
    "bg-[#253745]/15 text-[#11212D] border-[#253745]/30 dark:bg-[#4A5C6A]/35 dark:text-[#CCD0CF] dark:border-[#9BA8AB]/35";

  switch (norm) {
    case "pdf":
      return { label: "PDF", color: baseStyle };
    case "docx":
    case "doc":
      return { label: "DOCX", color: baseStyle };
    case "pptx":
    case "ppt":
      return { label: "PPTX", color: baseStyle };
    case "xlsx":
    case "csv":
      return { label: "SHEET", color: baseStyle };
    case "code":
    case "py":
    case "ts":
    case "tsx":
    case "js":
    case "json":
      return { label: "CODE", color: accentStyle };
    case "md":
    case "markdown":
      return { label: "MD", color: accentStyle };
    case "image":
    case "jpg":
    case "jpeg":
    case "png":
    case "webp":
      return { label: "IMAGE", color: baseStyle };
    case "audio":
    case "mp3":
    case "wav":
    case "flac":
      return { label: "AUDIO", color: baseStyle };
    case "video":
    case "mp4":
    case "mkv":
    case "webm":
      return { label: "VIDEO", color: baseStyle };
    case "text":
    case "txt":
      return { label: "TXT", color: baseStyle };
    default:
      return { label: norm.toUpperCase(), color: baseStyle };
  }
}
