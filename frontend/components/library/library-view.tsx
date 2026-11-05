"use client";

import React, { useEffect, useState } from "react";
import {
  FolderOpen,
  FolderPlus,
  Play,
  Trash2,
  RefreshCw,
  HardDrive,
  FileText,
  Clock,
  Layers,
  AlertCircle,
} from "lucide-react";
import { folderApi } from "@/lib/api";
import { FolderResponse } from "@/lib/types";
import { formatBytes, formatNumber, formatRelativeTime } from "@/lib/utils";
import { Button } from "../ui/button";
import { Dialog } from "../ui/dialog";
import { Input } from "../ui/input";

interface LibraryViewProps {
  onTriggerIndexingSuccess?: () => void;
}

export function LibraryView({ onTriggerIndexingSuccess }: LibraryViewProps) {
  const [folders, setFolders] = useState<FolderResponse[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Add folder modal state
  const [isAddOpen, setIsAddOpen] = useState(false);
  const [newFolderPath, setNewFolderPath] = useState("");
  const [isAdding, setIsAdding] = useState(false);
  const [addError, setAddError] = useState<string | null>(null);

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

  const handleToggleFolder = async (folder: FolderResponse) => {
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

  const handleAddFolder = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newFolderPath.trim()) return;

    setIsAdding(true);
    setAddError(null);
    try {
      const created = await folderApi.create({
        path: newFolderPath.trim(),
        enabled: true,
      });
      setFolders((prev) => [...prev, created]);
      setNewFolderPath("");
      setIsAddOpen(false);
      setActionMessage(`Folder registered: ${created.path}`);
      setTimeout(() => setActionMessage(null), 4000);
    } catch (err: unknown) {
      setAddError(err instanceof Error ? err.message : "Failed to add folder");
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
      });
      setActionMessage(`Indexing triggered for ${folder.path}`);
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
    <div className="p-6 sm:p-10 max-w-5xl mx-auto space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-6 border-b border-slate-200 dark:border-navy-800">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white">
            Indexed Library Folders
          </h1>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
            Manage local directories indexed by OmniSearch. Toggle active status or trigger updates on demand.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Button variant="outline" size="sm" onClick={fetchFolders} disabled={isLoading}>
            <RefreshCw className={`w-4 h-4 mr-1.5 ${isLoading ? "animate-spin" : ""}`} />
            Refresh
          </Button>

          <Button variant="primary" size="sm" onClick={() => setIsAddOpen(true)}>
            <FolderPlus className="w-4 h-4 mr-1.5" />
            Add Folder
          </Button>
        </div>
      </div>

      {/* Notification Toast Message if any */}
      {actionMessage && (
        <div className="p-3 rounded-xl bg-cyan-500/10 border border-cyan-500/20 text-xs text-cyan-600 dark:text-cyan-400 flex items-center justify-between">
          <span>{actionMessage}</span>
          <button onClick={() => setActionMessage(null)} className="font-semibold underline ml-2">
            Dismiss
          </button>
        </div>
      )}

      {/* Error state */}
      {error && (
        <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/20 text-xs text-red-500 flex items-center gap-2">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Folder Cards List */}
      {folders.length > 0 ? (
        <div className="grid grid-cols-1 gap-3.5">
          {folders.map((folder) => (
            <div
              key={folder.id}
              className="p-5 rounded-2xl bg-white dark:bg-navy-900 border border-slate-200 dark:border-navy-800 hover:border-slate-300 dark:hover:border-navy-700 shadow-sm transition-all flex flex-col md:flex-row md:items-center justify-between gap-4"
            >
              <div className="flex items-start gap-3.5 min-w-0">
                <div
                  className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 ${
                    folder.enabled
                      ? "bg-cyan-500/10 text-cyan-500 border border-cyan-500/20"
                      : "bg-slate-100 dark:bg-navy-800 text-slate-400 border border-slate-200 dark:border-navy-750"
                  }`}
                >
                  <FolderOpen className="w-5 h-5" />
                </div>

                <div className="min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100 font-mono truncate" title={folder.path}>
                      {folder.path}
                    </h3>
                    <span
                      className={`text-[10px] font-mono px-2 py-0.5 rounded-full font-medium ${
                        folder.enabled
                          ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20"
                          : "bg-slate-100 dark:bg-navy-800 text-slate-500 border border-slate-200 dark:border-navy-700"
                      }`}
                    >
                      {folder.enabled ? "Active" : "Disabled"}
                    </span>
                  </div>

                  {/* Metrics Row */}
                  <div className="flex items-center gap-4 mt-2 text-xs text-slate-500 dark:text-slate-400 flex-wrap">
                    <span className="flex items-center gap-1">
                      <FileText className="w-3.5 h-3.5 text-slate-400" />
                      {formatNumber(folder.file_count)} files
                    </span>
                    <span>•</span>
                    <span className="flex items-center gap-1">
                      <Layers className="w-3.5 h-3.5 text-slate-400" />
                      {formatNumber(folder.chunk_count)} chunks
                    </span>
                    <span>•</span>
                    <span className="flex items-center gap-1">
                      <HardDrive className="w-3.5 h-3.5 text-slate-400" />
                      {formatBytes(folder.total_size_bytes)}
                    </span>
                    <span>•</span>
                    <span className="flex items-center gap-1">
                      <Clock className="w-3.5 h-3.5 text-slate-400" />
                      Indexed {formatRelativeTime(folder.last_indexed_at)}
                    </span>
                  </div>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex items-center gap-2 shrink-0 self-end md:self-center">
                <Button
                  variant="outline"
                  size="xs"
                  onClick={() => handleToggleFolder(folder)}
                >
                  {folder.enabled ? "Disable" : "Enable"}
                </Button>

                <Button
                  variant="secondary"
                  size="xs"
                  onClick={() => handleIndexFolder(folder)}
                  title="Run indexing for this folder"
                >
                  <Play className="w-3 h-3 mr-1 text-cyan-500" />
                  Index
                </Button>

                <Button
                  variant="danger"
                  size="xs"
                  onClick={() => setFolderToDelete(folder)}
                  title="Remove folder from library"
                >
                  <Trash2 className="w-3 h-3 text-red-500" />
                </Button>
              </div>
            </div>
          ))}
        </div>
      ) : !isLoading ? (
        <div className="p-12 text-center rounded-2xl bg-white dark:bg-navy-900 border border-slate-200 dark:border-navy-800">
          <FolderPlus className="w-10 h-10 text-slate-400 dark:text-slate-500 mx-auto mb-3" />
          <h3 className="text-base font-semibold text-slate-900 dark:text-slate-100 mb-1">
            No Folders Added Yet
          </h3>
          <p className="text-xs text-slate-500 dark:text-slate-400 max-w-sm mx-auto mb-5">
            Add your documents directory, source code folder, or personal vault to begin indexing.
          </p>
          <Button variant="primary" size="sm" onClick={() => setIsAddOpen(true)}>
            <FolderPlus className="w-4 h-4 mr-1.5" />
            Add First Folder
          </Button>
        </div>
      ) : null}

      {/* Add Folder Modal Dialog */}
      <Dialog
        open={isAddOpen}
        onClose={() => setIsAddOpen(false)}
        title="Register Indexing Folder"
        description="Specify the local directory path you want OmniSearch to index."
      >
        <form onSubmit={handleAddFolder} className="space-y-4">
          <Input
            placeholder="e.g. C:\Users\Username\Documents"
            value={newFolderPath}
            onChange={(e) => setNewFolderPath(e.target.value)}
            disabled={isAdding}
            error={addError || undefined}
            autoFocus
          />

          <div className="flex justify-end gap-2 pt-2">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => setIsAddOpen(false)}
              disabled={isAdding}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              size="sm"
              isLoading={isAdding}
              disabled={!newFolderPath.trim()}
            >
              Register & Save
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
          <div className="p-3 rounded-xl bg-slate-50 dark:bg-navy-950 border border-slate-200 dark:border-navy-800 text-xs font-mono text-slate-700 dark:text-slate-300 break-all">
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
              Confirm Remove
            </Button>
          </div>
        </div>
      </Dialog>
    </div>
  );
}
