/**
 * Native File Actions Service for OmniSearch (Open File & Reveal in File Explorer).
 *
 * Implements safe, decoupled execution:
 * 1. Electron Desktop Mode: Uses secure window.omnisearch.openFile/revealFile via contextBridge.
 * 2. Browser Development Mode: Uses backend native system endpoint (/api/v1/system/open-file, /system/reveal-file)
 *    to invoke host OS default application / Explorer directly.
 * 3. Graceful Fallback: Returns structured error if the file does not exist or action fails.
 */

import { systemApi } from "../api";
import { FileActionResult } from "../types";

/**
 * Open the selected file using the operating system's default application.
 */
export async function openFile(filePath: string): Promise<FileActionResult> {
  if (!filePath || !filePath.trim()) {
    return { success: false, error: "Invalid file path" };
  }

  // 1. Electron Desktop Mode
  if (
    typeof window !== "undefined" &&
    window.omnisearch &&
    typeof window.omnisearch.openFile === "function"
  ) {
    try {
      return await window.omnisearch.openFile(filePath);
    } catch (err) {
      return {
        success: false,
        error: err instanceof Error ? err.message : String(err),
      };
    }
  }

  // 2. Browser Development Mode (FastAPI Host Proxy)
  try {
    const res = await systemApi.openFile(filePath);
    return res;
  } catch (err) {
    return {
      success: false,
      error:
        err instanceof Error
          ? err.message
          : "Failed to open file in default application",
    };
  }
}

/**
 * Reveal the selected file in Windows File Explorer (highlighted).
 */
export async function revealFile(filePath: string): Promise<FileActionResult> {
  if (!filePath || !filePath.trim()) {
    return { success: false, error: "Invalid file path" };
  }

  // 1. Electron Desktop Mode
  if (
    typeof window !== "undefined" &&
    window.omnisearch &&
    typeof window.omnisearch.revealFile === "function"
  ) {
    try {
      return await window.omnisearch.revealFile(filePath);
    } catch (err) {
      return {
        success: false,
        error: err instanceof Error ? err.message : String(err),
      };
    }
  }

  // 2. Browser Development Mode (FastAPI Host Proxy)
  try {
    const res = await systemApi.revealFile(filePath);
    return res;
  } catch (err) {
    return {
      success: false,
      error:
        err instanceof Error
          ? err.message
          : "Failed to reveal file in File Explorer",
    };
  }
}

