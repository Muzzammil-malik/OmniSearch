/**
 * Cross-platform Folder Picker Service for OmniSearch.
 *
 * Implements a clean, decoupled abstraction:
 * 1. Electron Desktop Mode: Uses the secure window.omnisearch.selectFolder() preload contextBridge.
 * 2. Browser Development Mode: Uses backend native dialog endpoint (/api/v1/system/pick-folder)
 *    to invoke the host OS native folder selection experience without faking pickers.
 * 3. Graceful Fallback: Returns structured error if native dialog cannot be displayed.
 */

import { systemApi } from "../api";
import { FolderPickerResult } from "./types";

export * from "./types";

/**
 * Invoke the operating system's native folder selection dialog.
 * Returns the selected absolute path, or indicates cancellation without error.
 */
export async function selectFolder(): Promise<FolderPickerResult> {
  // 1. Check for Electron native desktop bridge
  if (typeof window !== "undefined" && window.omnisearch && typeof window.omnisearch.selectFolder === "function") {
    try {
      const selectedPath = await window.omnisearch.selectFolder();
      if (!selectedPath) {
        return { path: null, canceled: true, mode: "electron" };
      }
      return { path: selectedPath, canceled: false, mode: "electron" };
    } catch (err) {
      return {
        path: null,
        canceled: false,
        error: err instanceof Error ? err.message : String(err),
        mode: "electron",
      };
    }
  }

  // 2. Check for backend native dialog capability (Browser development mode)
  try {
    const res = await systemApi.pickFolderNative();
    if (res.error) {
      return { path: null, canceled: false, error: res.error, mode: "browser_native" };
    }
    if (res.canceled || !res.path) {
      return { path: null, canceled: true, mode: "browser_native" };
    }
    return { path: res.path, canceled: false, mode: "browser_native" };
  } catch (err) {
    return {
      path: null,
      canceled: false,
      error: err instanceof Error ? err.message : "Native folder selection dialog could not be opened",
      mode: "browser_native",
    };
  }
}

