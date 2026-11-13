/**
 * Types for native OS integration and folder picker abstractions.
 */

export interface FolderPickerResult {
  path: string | null;
  canceled: boolean;
  error?: string;
  mode: "electron" | "browser_native" | "none";
}

