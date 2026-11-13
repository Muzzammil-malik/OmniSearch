"use client";

import React, { useEffect, useId, useRef, useState, useMemo } from "react";
import {
  Check,
  ChevronDown,
  Folder,
  FolderKanban,
  FolderPlus,
  Loader2,
} from "lucide-react";
import { AnimatePresence, motion } from "framer-motion";
import { FolderResponse } from "@/lib/types";
import { folderApi } from "@/lib/api";
import { cn } from "@/lib/utils";

interface LibraryScopeSelectorProps {
  selectedFolderId: number | null;
  onSelectFolderId: (folderId: number | null) => void;
  onOpenLibrary?: () => void;
  className?: string;
}

function getFolderBasename(folderPath: string): string {
  if (!folderPath) return "Folder";
  const parts = folderPath.replace(/\\/g, "/").split("/").filter(Boolean);
  return parts.length > 0 ? parts[parts.length - 1] : folderPath;
}

export function LibraryScopeSelector({
  selectedFolderId,
  onSelectFolderId,
  onOpenLibrary,
  className,
}: LibraryScopeSelectorProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [openUpward, setOpenUpward] = useState(true);
  const [folders, setFolders] = useState<FolderResponse[]>([]);
  const [isLoadingFolders, setIsLoadingFolders] = useState(false);
  const [focusedIndex, setFocusedIndex] = useState(-1);

  const containerRef = useRef<HTMLDivElement>(null);
  const triggerButtonRef = useRef<HTMLButtonElement>(null);
  const itemRefs = useRef<(HTMLButtonElement | null)[]>([]);
  const listboxId = useId();

  // Load folders on mount and when menu opens
  const fetchFolders = async () => {
    try {
      setIsLoadingFolders(true);
      const res = await folderApi.list();
      setFolders(res.folders || []);
    } catch {
      // Keep existing list on transient network error
    } finally {
      setIsLoadingFolders(false);
    }
  };

  useEffect(() => {
    fetchFolders();
  }, []);

  // Determine whether to open upward or downward based on space above container
  const updatePlacement = () => {
    if (!triggerButtonRef.current) return;
    const rect = triggerButtonRef.current.getBoundingClientRect();
    // If distance from trigger to viewport top is at least 260px, open upward
    setOpenUpward(rect.top >= 260);
  };

  const handleToggle = () => {
    if (!isOpen) {
      updatePlacement();
      fetchFolders();
    }
    setIsOpen((prev) => !prev);
  };

  // Close on click-outside and Escape key
  useEffect(() => {
    if (!isOpen) return;

    const handleClickOutside = (e: MouseEvent | TouchEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };

    const handleWindowKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setIsOpen(false);
        triggerButtonRef.current?.focus();
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    document.addEventListener("touchstart", handleClickOutside);
    window.addEventListener("keydown", handleWindowKeyDown);

    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("touchstart", handleClickOutside);
      window.removeEventListener("keydown", handleWindowKeyDown);
    };
  }, [isOpen]);

  // Active label & icon calculation
  const activeFolder = useMemo(
    () => folders.find((f) => f.id === selectedFolderId),
    [folders, selectedFolderId]
  );

  const currentLabel = activeFolder
    ? getFolderBasename(activeFolder.path)
    : "All Library Folders";

  // Item indexing: 0 = "All Library Folders", 1..N = Folders
  const totalOptions = 1 + folders.length;

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!isOpen) {
      if (e.key === "ArrowDown" || e.key === "ArrowUp" || e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        updatePlacement();
        setIsOpen(true);
        const idx = selectedFolderId === null
          ? 0
          : folders.findIndex((f) => f.id === selectedFolderId) + 1;
        setFocusedIndex(idx >= 0 ? idx : 0);
        setTimeout(() => itemRefs.current[idx >= 0 ? idx : 0]?.focus(), 0);
      }
      return;
    }

    if (e.key === "ArrowDown") {
      e.preventDefault();
      const nextIndex = (focusedIndex + 1) % totalOptions;
      setFocusedIndex(nextIndex);
      itemRefs.current[nextIndex]?.focus();
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      const nextIndex = focusedIndex <= 0 ? totalOptions - 1 : focusedIndex - 1;
      setFocusedIndex(nextIndex);
      itemRefs.current[nextIndex]?.focus();
    } else if (e.key === "Tab") {
      setIsOpen(false);
    }
  };

  const handleSelect = (folderId: number | null) => {
    onSelectFolderId(folderId);
    setIsOpen(false);
    triggerButtonRef.current?.focus();
  };

  return (
    <div ref={containerRef} className={cn("relative inline-block", className)}>
      {/* Compact Scope Button Trigger */}
      <button
        ref={triggerButtonRef}
        type="button"
        onClick={handleToggle}
        onKeyDown={handleKeyDown}
        aria-haspopup="listbox"
        aria-expanded={isOpen}
        aria-controls={listboxId}
        aria-label={`Search scope: ${currentLabel}`}
        title={`Search scope: ${currentLabel}`}
        className={cn(
          "inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium transition-all duration-150 select-none",
          "border border-[#9BA8AB]/70 dark:border-[#253745]",
          "bg-[#CCD0CF]/60 dark:bg-[#06141B]/70 hover:bg-[#CCD0CF] dark:hover:bg-[#11212D]",
          "text-[#06141B] dark:text-[#CCD0CF] hover:border-[#4A5C6A] dark:hover:border-[#4A5C6A]",
          selectedFolderId !== null &&
            "border-[#4A5C6A] dark:border-[#9BA8AB]/40 bg-[#D8DCDB] dark:bg-[#11212D] text-[#06141B] dark:text-[#CCD0CF] font-semibold"
        )}
      >
        {selectedFolderId === null ? (
          <FolderKanban className="w-3.5 h-3.5 text-yellow-500 dark:text-yellow-400 fill-yellow-500/20 dark:fill-yellow-400/20 shrink-0" />
        ) : (
          <Folder className="w-3.5 h-3.5 text-yellow-500 dark:text-yellow-400 fill-yellow-500/20 dark:fill-yellow-400/20 shrink-0" />
        )}

        <span className="truncate max-w-[190px] sm:max-w-[260px]">
          {currentLabel}
        </span>

        <ChevronDown
          className={cn(
            "w-3.5 h-3.5 text-[#4A5C6A] dark:text-[#9BA8AB] transition-transform duration-150 shrink-0",
            isOpen && (openUpward ? "-rotate-180" : "rotate-180")
          )}
        />
      </button>

      {/* Popover Menu */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            id={listboxId}
            role="listbox"
            tabIndex={-1}
            aria-label="Library folder scope options"
            initial={{ opacity: 0, y: openUpward ? 6 : -6, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: openUpward ? 4 : -4, scale: 0.98 }}
            transition={{ duration: 0.12, ease: "easeOut" }}
            className={cn(
              "absolute left-0 z-50 min-w-[260px] max-w-[340px] p-1.5 rounded-xl shadow-xl",
              "bg-[#E2E6E5] dark:bg-[#06141B] border border-[#9BA8AB] dark:border-[#253745]",
              openUpward ? "bottom-full mb-2" : "top-full mt-2"
            )}
          >
            {/* Header / Caption */}
            <div className="px-2.5 pt-1.5 pb-1 flex items-center justify-between text-[10px] font-mono uppercase tracking-wider text-[#4A5C6A] dark:text-[#9BA8AB]">
              <span>Search Scope</span>
              {isLoadingFolders && (
                <Loader2 className="w-3 h-3 animate-spin text-[#4A5C6A] dark:text-[#9BA8AB]" />
              )}
            </div>

            {/* Option 1: All Library Folders */}
            <button
              ref={(el) => {
                itemRefs.current[0] = el;
              }}
              type="button"
              role="option"
              aria-selected={selectedFolderId === null}
              onClick={() => handleSelect(null)}
              onKeyDown={handleKeyDown}
              className={cn(
                "w-full flex items-center justify-between gap-2.5 px-2.5 py-1.5 rounded-lg text-left text-xs transition-colors",
                selectedFolderId === null
                  ? "bg-[#CCD0CF] dark:bg-[#11212D] text-[#06141B] dark:text-[#CCD0CF] font-medium"
                  : "text-[#253745] dark:text-[#9BA8AB] hover:bg-[#CCD0CF]/50 dark:hover:bg-[#11212D]/60 hover:text-[#06141B] dark:hover:text-[#CCD0CF]"
              )}
            >
              <div className="flex items-center gap-2 min-w-0">
                <FolderKanban className="w-3.5 h-3.5 text-yellow-500 dark:text-yellow-400 fill-yellow-500/20 dark:fill-yellow-400/20 shrink-0" />
                <div className="min-w-0">
                  <div className="truncate">All Library Folders</div>
                  <div className="text-[10px] text-[#4A5C6A] dark:text-[#9BA8AB] truncate">
                    Search across all indexed locations
                  </div>
                </div>
              </div>
              {selectedFolderId === null && (
                <Check className="w-3.5 h-3.5 text-[#06141B] dark:text-[#CCD0CF] shrink-0" />
              )}
            </button>

            {/* Divider */}
            <div className="my-1 border-t border-[#9BA8AB]/40 dark:border-[#253745]" />

            {/* Registered Folders List */}
            <div className="max-h-56 overflow-y-auto space-y-0.5 pr-0.5">
              {folders.length === 0 ? (
                <div className="px-2.5 py-3 text-center">
                  <p className="text-[11px] text-[#4A5C6A] dark:text-[#9BA8AB] mb-1.5">
                    No folders registered in library yet.
                  </p>
                  {onOpenLibrary && (
                    <button
                      type="button"
                      onClick={() => {
                        setIsOpen(false);
                        onOpenLibrary();
                      }}
                      className="inline-flex items-center gap-1 text-[11px] font-medium text-[#06141B] dark:text-[#CCD0CF] underline underline-offset-2 hover:opacity-80"
                    >
                      <FolderPlus className="w-3 h-3 text-yellow-500 dark:text-yellow-400" />
                      Add folder in Library
                    </button>
                  )}
                </div>
              ) : (
                folders.map((folder, index) => {
                  const isSelected = selectedFolderId === folder.id;
                  const itemIndex = 1 + index;
                  const basename = getFolderBasename(folder.path);

                  return (
                    <button
                      key={folder.id}
                      ref={(el) => {
                        itemRefs.current[itemIndex] = el;
                      }}
                      type="button"
                      role="option"
                      aria-selected={isSelected}
                      onClick={() => handleSelect(folder.id)}
                      onKeyDown={handleKeyDown}
                      className={cn(
                        "w-full flex items-center justify-between gap-2.5 px-2.5 py-1.5 rounded-lg text-left text-xs transition-colors",
                        isSelected
                          ? "bg-[#CCD0CF] dark:bg-[#11212D] text-[#06141B] dark:text-[#CCD0CF] font-medium"
                          : "text-[#253745] dark:text-[#9BA8AB] hover:bg-[#CCD0CF]/50 dark:hover:bg-[#11212D]/60 hover:text-[#06141B] dark:hover:text-[#CCD0CF]"
                      )}
                    >
                      <div className="flex items-center gap-2 min-w-0">
                        <Folder className="w-3.5 h-3.5 text-yellow-500 dark:text-yellow-400 fill-yellow-500/20 dark:fill-yellow-400/20 shrink-0" />
                        <div className="min-w-0">
                          <div className="truncate font-medium">{basename}</div>
                          <div
                            className="text-[10px] text-[#4A5C6A] dark:text-[#9BA8AB] truncate font-mono"
                            title={folder.path}
                          >
                            {folder.path}
                          </div>
                        </div>
                      </div>
                      {isSelected && (
                        <Check className="w-3.5 h-3.5 text-[#06141B] dark:text-[#CCD0CF] shrink-0" />
                      )}
                    </button>
                  );
                })
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

