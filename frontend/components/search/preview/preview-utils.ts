/**
 * File preview categorization and capability detection.
 */

export type PreviewKind =
  | "image"
  | "video"
  | "audio"
  | "pdf"
  | "docx"
  | "code"
  | "markdown"
  | "table"
  | "text"
  | "unsupported";

const IMAGE_EXTENSIONS = new Set([
  "jpg",
  "jpeg",
  "png",
  "webp",
  "gif",
  "bmp",
  "svg",
  "tiff",
  "tif",
]);

const VIDEO_EXTENSIONS = new Set([
  "mp4",
  "webm",
  "mov",
  "mkv",
  "avi",
  "wmv",
  "m4v",
  "mpeg",
  "mpg",
]);

const AUDIO_EXTENSIONS = new Set([
  "mp3",
  "wav",
  "flac",
  "m4a",
  "aac",
  "ogg",
  "oga",
  "opus",
  "wma",
]);

const TABLE_EXTENSIONS = new Set(["csv", "tsv", "xlsx", "xls"]);

const CODE_EXTENSIONS = new Set([
  "py",
  "js",
  "ts",
  "tsx",
  "jsx",
  "java",
  "cpp",
  "c",
  "h",
  "cs",
  "go",
  "rs",
  "php",
  "css",
  "json",
  "xml",
  "yaml",
  "yml",
  "sql",
  "sh",
  "bat",
  "ps1",
]);

const TEXT_EXTENSIONS = new Set(["txt", "text", "log", "ini", "cfg", "conf", "html", "htm"]);

/**
 * Determine the preview kind for a given search result item.
 */
export function getPreviewKind(fileType?: string | null, filename?: string | null, contentType?: string | null): PreviewKind {
  const ext = (filename?.split(".").pop() || "").toLowerCase();
  const ftype = (fileType || "").toLowerCase();
  const ctype = (contentType || "").toLowerCase();

  if (ctype === "image" || ftype === "image" || IMAGE_EXTENSIONS.has(ext)) {
    return "image";
  }

  if (ctype === "video" || ftype === "video" || VIDEO_EXTENSIONS.has(ext)) {
    return "video";
  }

  if (ctype === "audio" || ftype === "audio" || AUDIO_EXTENSIONS.has(ext)) {
    return "audio";
  }

  if (ftype === "pdf" || ext === "pdf") {
    return "pdf";
  }

  if (ftype === "docx" || ext === "docx" || ext === "doc") {
    return "docx";
  }

  if (
    TABLE_EXTENSIONS.has(ext) ||
    ftype === "xlsx" ||
    ftype === "csv" ||
    ftype === "tsv" ||
    ftype === "sheet" ||
    ftype === "sheets" ||
    ftype === "spreadsheet" ||
    ftype === "table"
  ) {
    return "table";
  }

  if (ext === "md" || ext === "markdown" || ftype === "markdown" || ftype === "md") {
    return "markdown";
  }

  if (CODE_EXTENSIONS.has(ext) || ftype === "code") {
    return "code";
  }

  if (TEXT_EXTENSIONS.has(ext) || ftype === "text" || ftype === "pptx") {
    return "text";
  }

  return "unsupported";
}

