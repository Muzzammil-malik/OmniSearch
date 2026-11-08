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
  // Split on <mark> and </mark>
  const parts = html.split(/(<\/?mark>)/i);
  return parts
    .map((part) => {
      if (part.toLowerCase() === "<mark>") return "<mark>";
      if (part.toLowerCase() === "</mark>") return "</mark>";
      // Escape HTML entities in raw content
      return part
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
    })
    .join("");
}

export function getFileTypeBadge(fileType: string): { label: string; color: string } {
  const norm = fileType?.toLowerCase() || "unknown";
  switch (norm) {
    case "pdf":
      return { label: "PDF", color: "bg-red-500/10 text-red-400 border-red-500/20" };
    case "docx":
    case "doc":
      return { label: "DOCX", color: "bg-blue-500/10 text-blue-400 border-blue-500/20" };
    case "pptx":
    case "ppt":
      return { label: "PPTX", color: "bg-amber-500/10 text-amber-400 border-amber-500/20" };
    case "xlsx":
    case "csv":
      return { label: "SHEET", color: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20" };
    case "code":
    case "py":
    case "ts":
    case "tsx":
    case "js":
    case "json":
      return { label: "CODE", color: "bg-purple-500/10 text-purple-400 border-purple-500/20" };
    case "md":
    case "markdown":
      return { label: "MD", color: "bg-cyan-500/10 text-cyan-400 border-cyan-500/20" };
    case "image":
    case "jpg":
    case "jpeg":
    case "png":
    case "webp":
      return { label: "IMAGE", color: "bg-pink-500/10 text-pink-400 border-pink-500/20" };
    case "audio":
    case "mp3":
    case "wav":
    case "flac":
      return { label: "AUDIO", color: "bg-teal-500/10 text-teal-400 border-teal-500/20" };
    case "video":
    case "mp4":
    case "mkv":
    case "webm":
      return { label: "VIDEO", color: "bg-orange-500/10 text-orange-400 border-orange-500/20" };
    case "text":
    case "txt":
      return { label: "TXT", color: "bg-slate-500/10 text-slate-400 border-slate-500/20" };
    default:
      return { label: norm.toUpperCase(), color: "bg-slate-500/10 text-slate-400 border-slate-500/20" };
  }
}

