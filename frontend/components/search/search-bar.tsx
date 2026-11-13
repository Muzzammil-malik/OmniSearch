"use client";

import React, { useEffect, useId, useRef, useState } from "react";
import {
  Check,
  ChevronDown,
  FileCode,
  FileSpreadsheet,
  FileText,
  Film,
  Image as ImageIcon,
  Music,
  Presentation,
  Search,
  SlidersHorizontal,
  X,
} from "lucide-react";
import { AnimatePresence, motion } from "framer-motion";
import { SearchMode } from "@/lib/types";
import { cn } from "@/lib/utils";
import { LibraryScopeSelector } from "./library-scope-selector";

interface SearchBarProps {
  query: string;
  onQueryChange: (query: string) => void;
  mode: SearchMode;
  onModeChange: (mode: SearchMode) => void;
  selectedFileType: string | null;
  onSelectFileType: (fileType: string | null) => void;
  selectedFolderId: number | null;
  onSelectFolderId: (folderId: number | null) => void;
  onOpenLibrary?: () => void;
  isLoading: boolean;
  onSearchSubmit?: () => void;
  onClear: () => void;
}

interface FormatOption {
  label: string;
  value: string | null;
  icon: React.ComponentType<{ className?: string }>;
}

interface FormatGroup {
  name: string;
  options: FormatOption[];
}

const FORMAT_GROUPS: FormatGroup[] = [
  {
    name: "FORMAT",
    options: [
      { label: "All Formats", value: null, icon: SlidersHorizontal },
    ],
  },
  {
    name: "DOCUMENTS",
    options: [
      { label: "PDF", value: "pdf", icon: FileText },
      { label: "DOCX", value: "docx", icon: FileText },
      { label: "PPTX", value: "pptx", icon: Presentation },
      { label: "Sheets", value: "xlsx", icon: FileSpreadsheet },
    ],
  },
  {
    name: "TEXT & CODE",
    options: [
      { label: "Code", value: "code", icon: FileCode },
      { label: "Markdown", value: "md", icon: FileText },
      { label: "Text", value: "text", icon: FileText },
    ],
  },
  {
    name: "MEDIA",
    options: [
      { label: "Images", value: "image", icon: ImageIcon },
      { label: "Audio", value: "audio", icon: Music },
      { label: "Video", value: "video", icon: Film },
    ],
  },
];

const ALL_FORMAT_OPTIONS = FORMAT_GROUPS.flatMap((group) => group.options);

const SEARCH_MODES: { value: SearchMode; label: string; description: string }[] = [
  {
    value: "hybrid",
    label: "Hybrid",
    description: "Combined lexical BM25 and vector similarity ranking",
  },
  {
    value: "keyword",
    label: "Keyword",
    description: "Exact SQLite FTS5 lexical matching",
  },
  {
    value: "semantic",
    label: "Semantic",
    description: "Conceptual vector similarity retrieval",
  },
];

export function SearchBar({
  query,
  onQueryChange,
  mode,
  onModeChange,
  selectedFileType,
  onSelectFileType,
  selectedFolderId,
  onSelectFolderId,
  onOpenLibrary,
  isLoading,
  onSearchSubmit,
  onClear,
}: SearchBarProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const popoverRef = useRef<HTMLDivElement>(null);
  const triggerButtonRef = useRef<HTMLButtonElement>(null);
  const itemRefs = useRef<(HTMLButtonElement | null)[]>([]);
  const listboxId = useId();

  const [isFormatOpen, setIsFormatOpen] = useState(false);
  const [focusedIndex, setFocusedIndex] = useState<number>(-1);

  const activeFormatOption =
    ALL_FORMAT_OPTIONS.find((opt) => opt.value === selectedFileType) ||
    ALL_FORMAT_OPTIONS[0];
  const isFilterActive = selectedFileType !== null;

  // Global Ctrl+K / Cmd+K shortcut to focus search
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        inputRef.current?.focus();
        inputRef.current?.select();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  // Click-outside and Escape key listener for the Format popover
  useEffect(() => {
    if (!isFormatOpen) return;

    const handleClickOutside = (e: MouseEvent | TouchEvent) => {
      if (popoverRef.current && !popoverRef.current.contains(e.target as Node)) {
        setIsFormatOpen(false);
      }
    };

    const handleWindowKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setIsFormatOpen(false);
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
  }, [isFormatOpen]);

  // Handle keyboard navigation inside the popover
  const handleFormatPopoverKeyDown = (e: React.KeyboardEvent) => {
    if (!isFormatOpen) {
      if (e.key === "ArrowDown" || e.key === "ArrowUp" || e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        setIsFormatOpen(true);
        const currentIndex = ALL_FORMAT_OPTIONS.findIndex(
          (opt) => opt.value === selectedFileType
        );
        const nextIndex = currentIndex >= 0 ? currentIndex : 0;
        setFocusedIndex(nextIndex);
        setTimeout(() => itemRefs.current[nextIndex]?.focus(), 0);
      }
      return;
    }

    if (e.key === "ArrowDown") {
      e.preventDefault();
      const nextIndex = (focusedIndex + 1) % ALL_FORMAT_OPTIONS.length;
      setFocusedIndex(nextIndex);
      itemRefs.current[nextIndex]?.focus();
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      const nextIndex =
        focusedIndex <= 0 ? ALL_FORMAT_OPTIONS.length - 1 : focusedIndex - 1;
      setFocusedIndex(nextIndex);
      itemRefs.current[nextIndex]?.focus();
    } else if (e.key === "Tab") {
      setIsFormatOpen(false);
    }
  };

  const handleInputKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && onSearchSubmit) {
      e.preventDefault();
      onSearchSubmit();
    } else if (e.key === "Escape") {
      onClear();
      inputRef.current?.blur();
    }
  };

  const handleSelectOption = (value: string | null) => {
    onSelectFileType(value);
    setIsFormatOpen(false);
    triggerButtonRef.current?.focus();
  };

  return (
    <div className="w-full space-y-2.5">
      {/* Search Scope Selector immediately above the search input */}
      <div className="flex items-center justify-between">
        <LibraryScopeSelector
          selectedFolderId={selectedFolderId}
          onSelectFolderId={onSelectFolderId}
          onOpenLibrary={onOpenLibrary}
        />
      </div>

      {/* Prominent Search Field Container */}
      <div className="relative flex items-center w-full rounded-xl bg-[#E2E6E5] dark:bg-[#06141B] border border-[#9BA8AB] dark:border-[#253745] shadow-subtle hover:border-[#4A5C6A] dark:hover:border-[#4A5C6A] focus-within:border-[#06141B] dark:focus-within:border-[#9BA8AB] focus-within:ring-1 focus-within:ring-[#06141B]/20 dark:focus-within:ring-[#9BA8AB]/25 transition-all duration-150">
        {/* Left Search Icon or Restrained Loading Spinner */}
        <div className="pl-4 pr-3 text-[#4A5C6A] dark:text-[#9BA8AB] flex items-center justify-center shrink-0">
          {isLoading ? (
            <div
              className="w-4 h-4 border-[1.75px] border-[#4A5C6A]/35 border-t-[#06141B] dark:border-t-[#CCD0CF] rounded-full animate-spin"
              aria-label="Searching"
            />
          ) : (
            <Search className="w-4 h-4 stroke-[1.75]" />
          )}
        </div>

        {/* Search Input */}
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => onQueryChange(e.target.value)}
          onKeyDown={handleInputKeyDown}
          aria-label="Search local files and documents"
          placeholder="Search documents, media, code, and everything in between..."
          className="flex-1 bg-transparent py-3.5 pr-3 text-[15px] text-[#06141B] dark:text-[#CCD0CF] placeholder:text-[#4A5C6A] dark:placeholder:text-[#4A5C6A] focus:outline-none"
        />

        {/* Right Controls: Clear + Keyboard Shortcut + Search Action Pill */}
        <div className="flex items-center gap-2 pr-3 shrink-0">
          {query && (
            <button
              type="button"
              onClick={onClear}
              className="inline-flex items-center justify-center h-7 w-7 rounded-full text-[#4A5C6A] dark:text-[#9BA8AB] hover:text-[#06141B] dark:hover:text-[#CCD0CF] hover:bg-[#06141B]/[0.07] dark:hover:bg-[#253745] transition-colors"
              title="Clear search (Esc)"
              aria-label="Clear search query"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}

          <kbd className="hidden sm:inline-flex items-center px-2 py-0.5 rounded text-[11px] font-mono text-[#4A5C6A] dark:text-[#9BA8AB] bg-[#CCD0CF] dark:bg-[#11212D] border border-[#9BA8AB] dark:border-[#253745]">
            Ctrl K
          </kbd>

          {query.trim().length > 0 && onSearchSubmit && (
            <button
              type="button"
              onClick={onSearchSubmit}
              className="px-3.5 py-1.5 rounded-full text-xs font-medium bg-[#06141B] text-[#CCD0CF] hover:bg-[#11212D] dark:bg-[#CCD0CF] dark:text-[#06141B] dark:hover:bg-[#9BA8AB] transition-colors"
            >
              Search
            </button>
          )}
        </div>
      </div>

      {/* Search Mode Controls + Compact Format Popover Row */}
      <div className="flex flex-wrap items-center justify-between gap-3 pt-0.5">
        {/* Search Mode Controls (Pill Segmented Group) */}
        <div className="flex items-center gap-2 shrink-0">
          <span className="text-xs font-medium text-[#4A5C6A] dark:text-[#9BA8AB] select-none">
            Mode
          </span>
          <div
            role="group"
            aria-label="Search retrieval mode"
            className="inline-flex items-center bg-[#D8DCDB] dark:bg-[#06141B] p-0.5 rounded-full border border-[#9BA8AB] dark:border-[#253745]"
          >
            {SEARCH_MODES.map((m) => {
              const isActive = mode === m.value;
              return (
                <button
                  key={m.value}
                  type="button"
                  onClick={() => onModeChange(m.value)}
                  title={m.description}
                  className={cn(
                    "px-3 py-1 rounded-full text-xs font-medium transition-colors duration-150 whitespace-nowrap",
                    isActive
                      ? "bg-[#06141B] text-[#CCD0CF] dark:bg-[#CCD0CF] dark:text-[#06141B]"
                      : "text-[#253745] dark:text-[#9BA8AB] hover:text-[#06141B] dark:hover:text-[#CCD0CF]"
                  )}
                >
                  {m.label}
                </button>
              );
            })}
          </div>
        </div>

        {/* Refined Format Dropdown/Popover Control */}
        <div
          ref={popoverRef}
          className="relative inline-block text-left shrink-0"
          onKeyDown={handleFormatPopoverKeyDown}
        >
          <button
            ref={triggerButtonRef}
            type="button"
            onClick={() => {
              setIsFormatOpen((prev) => !prev);
              if (!isFormatOpen) {
                const currentIndex = ALL_FORMAT_OPTIONS.findIndex(
                  (opt) => opt.value === selectedFileType
                );
                setFocusedIndex(currentIndex >= 0 ? currentIndex : 0);
              }
            }}
            aria-haspopup="listbox"
            aria-expanded={isFormatOpen}
            aria-controls={isFormatOpen ? listboxId : undefined}
            aria-label={`Filter by file format, currently ${activeFormatOption.label}`}
            className={cn(
              "inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium transition-colors duration-150 border select-none",
              isFilterActive
                ? "bg-[#06141B] text-[#CCD0CF] border-[#06141B] dark:bg-[#CCD0CF] dark:text-[#06141B] dark:border-[#CCD0CF]"
                : isFormatOpen
                ? "bg-[#CCD0CF] dark:bg-[#253745] text-[#06141B] dark:text-[#CCD0CF] border-[#4A5C6A]"
                : "bg-transparent text-[#253745] dark:text-[#9BA8AB] border-[#9BA8AB] dark:border-[#253745] hover:border-[#4A5C6A] dark:hover:border-[#4A5C6A] hover:text-[#06141B] dark:hover:text-[#CCD0CF]"
            )}
          >
            <span className={cn(isFilterActive ? "opacity-80" : "text-[#4A5C6A] dark:text-[#9BA8AB]")}>
              Format
            </span>
            <span
              className={cn(isFilterActive ? "opacity-60" : "text-[#4A5C6A] dark:text-[#9BA8AB]")}
              aria-hidden="true"
            >
              ·
            </span>
            <span className={cn(isFilterActive && "font-semibold")}>
              {activeFormatOption.label}
            </span>
            <ChevronDown
              className={cn(
                "w-3 h-3 transition-transform duration-150",
                isFilterActive ? "opacity-80" : "text-[#4A5C6A] dark:text-[#9BA8AB]",
                isFormatOpen && "rotate-180"
              )}
            />
          </button>

          {/* Grouped Format Options Popover Menu */}
          <AnimatePresence>
            {isFormatOpen && (
              <motion.div
                id={listboxId}
                role="listbox"
                aria-label="Filter by file format"
                tabIndex={-1}
                initial={{ opacity: 0, y: -4, scale: 0.98 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: -4, scale: 0.98 }}
                transition={{ duration: 0.14, ease: [0.16, 1, 0.3, 1] }}
                className="absolute right-0 mt-1.5 w-56 max-h-[380px] overflow-y-auto rounded-xl bg-[#D8DCDB] dark:bg-[#11212D] border border-[#9BA8AB] dark:border-[#253745] p-1.5 shadow-modal z-50 focus:outline-none"
              >
                {FORMAT_GROUPS.map((group, groupIdx) => {
                  return (
                    <div key={group.name} className={cn(groupIdx > 0 && "mt-1 pt-1 border-t border-[#9BA8AB]/40 dark:border-[#253745]")}>
                      <div className="px-2.5 pt-1.5 pb-1 text-[10px] font-mono uppercase tracking-widest text-[#4A5C6A] dark:text-[#9BA8AB] select-none font-semibold">
                        {group.name}
                      </div>
                      <div className="space-y-0.5">
                        {group.options.map((option) => {
                          const isSelected = selectedFileType === option.value;
                          const flatIndex = ALL_FORMAT_OPTIONS.findIndex(
                            (opt) => opt.value === option.value
                          );
                          const Icon = option.icon;

                          return (
                            <button
                              key={option.label}
                              ref={(el) => {
                                itemRefs.current[flatIndex] = el;
                              }}
                              role="option"
                              aria-selected={isSelected}
                              type="button"
                              onClick={() => handleSelectOption(option.value)}
                              className={cn(
                                "w-full flex items-center justify-between px-2.5 py-1.5 rounded-lg text-xs font-medium text-left transition-colors duration-100 outline-none",
                                isSelected
                                  ? "bg-[#06141B] text-[#CCD0CF] dark:bg-[#CCD0CF] dark:text-[#06141B]"
                                  : "text-[#253745] dark:text-[#CCD0CF] hover:bg-[#CCD0CF]/75 dark:hover:bg-[#253745]/70 hover:text-[#06141B] dark:hover:text-[#CCD0CF] focus:bg-[#CCD0CF]/75 dark:focus:bg-[#253745]/70 focus:text-[#06141B] dark:focus:text-[#CCD0CF]"
                              )}
                            >
                              <div className="flex items-center gap-2 min-w-0">
                                <Icon
                                  className={cn(
                                    "w-3.5 h-3.5 shrink-0",
                                    isSelected
                                      ? "text-current"
                                      : "text-[#4A5C6A] dark:text-[#9BA8AB]"
                                  )}
                                />
                                <span className="truncate">{option.label}</span>
                              </div>
                              {isSelected && (
                                <Check className="w-3.5 h-3.5 shrink-0 ml-2" />
                              )}
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  );
                })}
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
}
