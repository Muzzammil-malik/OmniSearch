"use client";

import React, { useEffect, useState, useRef } from "react";
import {
  FolderPlus,
  Play,
  Trash2,
  RefreshCw,
  MoreHorizontal,
  Power,
} from "lucide-react";
import { motion } from "framer-motion";
import { folderApi } from "@/lib/api";
import { FolderResponse } from "@/lib/types";
import { formatBytes, formatNumber, formatRelativeTime } from "@/lib/utils";
import { selectFolder } from "@/lib/native/folder-picker";
import { Button } from "../ui/button";
import { Dialog } from "../ui/dialog";
import { Input } from "../ui/input";
import { Skeleton } from "../ui/skeleton";

interface LibraryViewProps {
  onTriggerIndexingSuccess?: () => void;
}

export function LibraryView({ onTriggerIndexingSuccess }: LibraryViewProps) {
  const [folders, setFolders] = useState<FolderResponse[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Overflow menu state
  const [openMenuFolderId, setOpenMenuFolderId] = useState<number | null>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  // Folder picker & manual fallback state
  const [isAdding, setIsAdding] = useState(false);
  const [isManualFallbackOpen, setIsManualFallbackOpen] = useState(false);
  const [manualFolderPath, setManualFolderPath] = useState("");
  const [manualAddError, setManualAddError] = useState<string | null>(null);

  // Delete folder confirmation modal state
  const [folderToDelete, setFolderToDelete] = useState<FolderResponse | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  // Action status message
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  const fetchFolders = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await folderApi.list();
      setFolders(res.folders);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load folders");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchFolders();
  }, []);

  // Close overflow menu when clicking outside
  useEffect(() => {
    const handleOutsideClick = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setOpenMenuFolderId(null);
      }
    };
    document.addEventListener("mousedown", handleOutsideClick);
    return () => document.removeEventListener("mousedown", handleOutsideClick);
  }, []);

  const handleToggleFolder = async (folder: FolderResponse) => {
    setOpenMenuFolderId(null);
    try {
      const updated = await folderApi.update(folder.id, {
        enabled: !folder.enabled,
      });
      setFolders((prev) =>
        prev.map((f) => (f.id === updated.id ? updated : f))
      );
    } catch (err: unknown) {
      setActionMessage(
        `Failed to update folder: ${err instanceof Error ? err.message : "Error"}`
      );
    }
  };

  const registerAndIndexFolder = async (folderPath: string) => {
    const created = await folderApi.create({
      path: folderPath.trim(),
      enabled: true,
    });
    setFolders((prev) => [...prev, created]);
    setActionMessage(`Folder registered: ${created.path}`);
    setTimeout(() => setActionMessage(null), 4000);

    // Automatically initiate initial indexing on the newly added folder
    try {
      await folderApi.triggerIndex(created.id, {
        force_reindex: false,
        reconcile_deleted: true,
        generate_embeddings: true,
        background: true,
      });
      if (onTriggerIndexingSuccess) {
        onTriggerIndexingSuccess();
      }
    } catch (indexErr) {
      console.warn("Initial indexing trigger notice:", indexErr);
    }
    fetchFolders();
  };

  const handleOpenFolderPicker = async () => {
    if (isAdding) return;
    setIsAdding(true);
    setActionMessage(null);
    try {
      const result = await selectFolder();

      // Normal user cancellation: leave library unchanged without error
      if (result.canceled || !result.path) {
        if (result.error) {
          // Native dialog could not be invoked (e.g. headless environment)
          setIsManualFallbackOpen(true);
        }
        return;
      }

      await registerAndIndexFolder(result.path);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to add folder";
      setActionMessage(`Could not add folder: ${msg}`);
      setTimeout(() => setActionMessage(null), 6000);
    } finally {
      setIsAdding(false);
    }
  };

  const handleManualAddSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!manualFolderPath.trim()) return;
    setIsAdding(true);
    setManualAddError(null);
    try {
      await registerAndIndexFolder(manualFolderPath.trim());
      setManualFolderPath("");
      setIsManualFallbackOpen(false);
    } catch (err: unknown) {
      setManualAddError(err instanceof Error ? err.message : "Failed to add folder");
    } finally {
      setIsAdding(false);
    }
  };

  const handleDeleteFolder = async () => {
    if (!folderToDelete) return;
    setIsDeleting(true);
    try {
      await folderApi.delete(folderToDelete.id);
      setFolders((prev) => prev.filter((f) => f.id !== folderToDelete.id));
      setFolderToDelete(null);
      setActionMessage(`Folder removed: ${folderToDelete.path}`);
      setTimeout(() => setActionMessage(null), 4000);
    } catch (err: unknown) {
      setActionMessage(
        `Failed to delete folder: ${err instanceof Error ? err.message : "Error"}`
      );
    } finally {
      setIsDeleting(false);
    }
  };

  const handleIndexFolder = async (folder: FolderResponse) => {
    try {
      await folderApi.triggerIndex(folder.id, {
        force_reindex: false,
        reconcile_deleted: true,
        generate_embeddings: true,
        background: true,
      });
      setActionMessage(`Indexing started for ${folder.path}`);
      setTimeout(() => setActionMessage(null), 4000);
      if (onTriggerIndexingSuccess) {
        onTriggerIndexingSuccess();
      }
      fetchFolders();
    } catch (err: unknown) {
      setActionMessage(
        `Failed to start indexing: ${err instanceof Error ? err.message : "Error"}`
      );
    }
  };

  return (
    <div className="px-6 sm:px-10 py-8 sm:py-10 max-w-5xl mx-auto space-y-8">
      {/* Editorial Section Header */}
      <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4 pb-6 border-b border-[#9BA8AB] dark:border-[#253745]">
        <div>
          <p className="text-[11px] font-mono uppercase tracking-widest text-[#4A5C6A] dark:text-[#9BA8AB] mb-1.5">
            Local Corpus
          </p>
          <h1 className="text-2xl sm:text-3xl font-serif font-normal tracking-tight text-[#06141B] dark:text-[#CCD0CF]">
            Library Folders
          </h1>
          <p className="text-xs sm:text-sm text-[#253745] dark:text-[#9BA8AB] mt-1">
            Manage the local directories monitored and indexed by OmniSearch.
          </p>
        </div>

        <div className="flex items-center gap-2.5 shrink-0">
          <Button variant="outline" size="sm" onClick={fetchFolders} disabled={isLoading}>
            <RefreshCw className={`w-3.5 h-3.5 mr-1.5 ${isLoading ? "animate-spin" : ""}`} />
            Refresh
          </Button>

          <Button
            variant="primary"
            size="sm"
            onClick={handleOpenFolderPicker}
            isLoading={isAdding}
            disabled={isAdding}
          >
            <FolderPlus className="w-3.5 h-3.5 mr-1.5" />
            Add folder
          </Button>
        </div>
      </div>

      {/* Status Notice */}
      {actionMessage && (
        <div className="px-4 py-3 rounded-xl bg-[#D8DCDB] dark:bg-[#06141B]/65 border border-[#9BA8AB] dark:border-[#253745] text-xs text-[#06141B] dark:text-[#CCD0CF] flex items-center justify-between gap-4">
          <span>{actionMessage}</span>
          <button
            type="button"
            onClick={() => setActionMessage(null)}
            className="px-2.5 py-0.5 rounded-full text-[11px] font-medium text-[#253745] dark:text-[#9BA8AB] hover:text-[#06141B] dark:hover:text-[#CCD0CF]"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Error State */}
      {error && (
        <div className="p-4 rounded-xl bg-[#D8DCDB] dark:bg-[#06141B]/65 border border-[#9b2226]/30 text-xs text-[#9b2226] dark:text-[#f2b8b5] flex items-center justify-between gap-4">
          <span className="font-mono">{error}</span>
          <Button variant="secondary" size="xs" onClick={fetchFolders}>
            Retry
          </Button>
        </div>
      )}

      {/* Loading State */}
      {isLoading && folders.length === 0 ? (
        <div className="space-y-3" aria-label="Loading library folders">
          {[0, 1, 2].map((i) => (
            <div
              key={i}
              className="p-5 rounded-xl bg-[#D8DCDB] dark:bg-[#06141B]/55 border border-[#9BA8AB] dark:border-[#253745] flex items-center justify-between gap-4"
            >
              <div className="space-y-2 flex-1">
                <Skeleton className="h-4 w-72" />
                <Skeleton className="h-3 w-96" />
              </div>
              <Skeleton className="h-8 w-24 rounded-full" />
            </div>
          ))}
        </div>
      ) : folders.length > 0 ? (
        <div className="space-y-3">
          {folders.map((folder, index) => (
            <motion.div
              key={folder.id}
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{
                duration: 0.18,
                delay: Math.min(index * 0.03, 0.15),
                ease: [0.16, 1, 0.3, 1],
              }}
              className="p-5 rounded-xl bg-[#D8DCDB] dark:bg-[#06141B]/55 border border-[#9BA8AB] dark:border-[#253745] hover:border-[#4A5C6A] dark:hover:border-[#4A5C6A] transition-colors flex flex-col md:flex-row md:items-center justify-between gap-4 relative"
            >
              <div className="min-w-0 flex-1">
                <div className="flex items-baseline gap-2.5 flex-wrap">
                  <h3
                    className="text-sm font-medium text-[#06141B] dark:text-[#CCD0CF] font-mono truncate"
                    title={folder.path}
                  >
                    {folder.path}
                  </h3>
                  <span aria-hidden="true" className="text-[#4A5C6A] text-xs">
                    ·
                  </span>
                  <span
                    className={
                      folder.enabled
                        ? "text-xs font-medium text-[#2d6a4f] dark:text-[#74c69d]"
                        : "text-xs font-medium text-[#4A5C6A] dark:text-[#9BA8AB]"
                    }
                  >
                    {folder.enabled ? "Active" : "Disabled"}
                  </span>
                </div>

                {/* Unboxed Tabular Metrics Row */}
                <div className="flex items-center gap-2 mt-2 text-xs text-[#253745] dark:text-[#9BA8AB] flex-wrap font-mono tabular-nums">
                  <span>{formatNumber(folder.file_count)} files</span>
                  <span aria-hidden="true" className="text-[#4A5C6A]">
                    ·
                  </span>
                  <span>{formatNumber(folder.chunk_count)} chunks</span>
                  <span aria-hidden="true" className="text-[#4A5C6A]">
                    ·
                  </span>
                  <span>{formatBytes(folder.total_size_bytes)}</span>
                  <span aria-hidden="true" className="text-[#4A5C6A]">
                    ·
                  </span>
                  <span className="font-sans">
                    Indexed {formatRelativeTime(folder.last_indexed_at)}
                  </span>
                </div>
              </div>

              {/* Action Controls (Pill-shaped buttons) */}
              <div className="flex items-center gap-2 shrink-0 self-end md:self-center">
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => handleIndexFolder(folder)}
                  title="Index this folder now"
                >
                  <Play className="w-3 h-3 mr-1.5" />
                  Index folder
                </Button>

                <div className="relative">
                  <button
                    type="button"
                    onClick={() =>
                      setOpenMenuFolderId(
                        openMenuFolderId === folder.id ? null : folder.id
                      )
                    }
                    className="inline-flex items-center justify-center h-8 w-8 rounded-full border border-[#9BA8AB] dark:border-[#253745] text-[#253745] dark:text-[#9BA8AB] hover:text-[#06141B] dark:hover:text-[#CCD0CF] hover:bg-[#06141B]/[0.06] dark:hover:bg-[#253745] transition-colors"
                    title="Folder options"
                    aria-label="Folder options"
                  >
                    <MoreHorizontal className="w-4 h-4" />
                  </button>

                  {openMenuFolderId === folder.id && (
                    <div
                      ref={menuRef}
                      className="absolute right-0 top-full mt-1.5 w-48 rounded-xl bg-[#E2E6E5] dark:bg-[#06141B] border border-[#9BA8AB] dark:border-[#4A5C6A] shadow-modal p-1.5 z-30 space-y-0.5"
                    >
                      <button
                        type="button"
                        onClick={() => handleToggleFolder(folder)}
                        className="w-full flex items-center gap-2 px-3 py-1.5 rounded-full text-xs text-[#06141B] dark:text-[#CCD0CF] hover:bg-[#9BA8AB]/40 dark:hover:bg-[#253745] transition-colors text-left"
                      >
                        <Power className="w-3.5 h-3.5 text-[#4A5C6A] dark:text-[#9BA8AB]" />
                        <span>
                          {folder.enabled ? "Disable indexing" : "Enable indexing"}
                        </span>
                      </button>

                      <div className="my-1 border-t border-[#9BA8AB]/60 dark:border-[#253745]" />

                      <button
                        type="button"
                        onClick={() => {
                          setOpenMenuFolderId(null);
                          setFolderToDelete(folder);
                        }}
                        className="w-full flex items-center gap-2 px-3 py-1.5 rounded-full text-xs text-[#9b2226] dark:text-[#f2b8b5] hover:bg-[#9b2226]/10 transition-colors text-left"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                        <span>Remove folder...</span>
                      </button>
                    </div>
                  )}
                </div>
              </div>
            </motion.div>
          ))}
        </div>
      ) : (
        <div className="p-12 text-center rounded-xl bg-[#D8DCDB] dark:bg-[#06141B]/55 border border-[#9BA8AB] dark:border-[#253745]">
          <p className="text-[11px] font-mono uppercase tracking-widest text-[#4A5C6A] dark:text-[#9BA8AB] mb-2">
            Empty Library
          </p>
          <h3 className="text-lg font-serif font-medium text-[#06141B] dark:text-[#CCD0CF] mb-1.5">
            No directories registered yet
          </h3>
          <p className="text-xs text-[#253745] dark:text-[#9BA8AB] max-w-sm mx-auto mb-6 leading-relaxed">
            Register a local directory containing documents, notes, spreadsheets, or codebases to begin indexing.
          </p>
          <Button
            variant="primary"
            size="sm"
            onClick={handleOpenFolderPicker}
            isLoading={isAdding}
            disabled={isAdding}
          >
            <FolderPlus className="w-3.5 h-3.5 mr-1.5" />
            Add first folder
          </Button>
        </div>
      )}

      {/* Manual Path Entry Fallback Modal (only displayed if native OS picker is unavailable) */}
      <Dialog
        open={isManualFallbackOpen}
        onClose={() => setIsManualFallbackOpen(false)}
        title="Register Indexing Folder"
        description="The native folder selection dialog could not be displayed. You can specify the local filesystem directory path manually:"
      >
        <form onSubmit={handleManualAddSubmit} className="space-y-4">
          <Input
            placeholder="e.g. C:\Users\Username\Documents"
            value={manualFolderPath}
            onChange={(e) => setManualFolderPath(e.target.value)}
            disabled={isAdding}
            error={manualAddError || undefined}
            autoFocus
          />

          <div className="flex justify-end gap-2 pt-2">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => setIsManualFallbackOpen(false)}
              disabled={isAdding}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              size="sm"
              isLoading={isAdding}
              disabled={!manualFolderPath.trim()}
            >
              Register folder
            </Button>
          </div>
        </form>
      </Dialog>

      {/* Confirm Delete Folder Modal Dialog */}
      <Dialog
        open={Boolean(folderToDelete)}
        onClose={() => setFolderToDelete(null)}
        title="Unregister Folder"
        description="Are you sure you want to remove this folder from OmniSearch? Indexed chunks will be removed from future searches."
      >
        <div className="space-y-4">
          <div className="p-3.5 rounded-xl bg-[#E2E6E5] dark:bg-[#06141B] border border-[#9BA8AB] dark:border-[#253745] text-xs font-mono text-[#06141B] dark:text-[#CCD0CF] break-all">
            {folderToDelete?.path}
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => setFolderToDelete(null)}
              disabled={isDeleting}
            >
              Cancel
            </Button>
            <Button
              type="button"
              variant="danger"
              size="sm"
              onClick={handleDeleteFolder}
              isLoading={isDeleting}
            >
              Confirm remove
            </Button>
          </div>
        </div>
      </Dialog>
    </div>
  );
}
