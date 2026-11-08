"use client";

import React, { useEffect } from "react";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";

interface DialogProps {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  children: React.ReactNode;
  className?: string;
}

export function Dialog({
  open,
  onClose,
  title,
  description,
  children,
  className,
}: DialogProps) {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
      }
    };
    if (open) {
      window.addEventListener("keydown", handleKeyDown);
      document.body.style.overflow = "hidden";
    }
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = "unset";
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Deep blue-black backdrop per design.md */}
      <div
        className="fixed inset-0 bg-claude-surface-dark/75 backdrop-blur-xs transition-opacity animate-in fade-in"
        onClick={onClose}
      />

      {/* Dialog content panel */}
      <div
        className={cn(
          "relative z-10 w-full max-w-lg rounded-lg bg-claude-canvas dark:bg-claude-surface-dark-elevated border border-claude-hairline dark:border-claude-surface-dark-soft p-6 shadow-surface transition-all animate-in zoom-in-95",
          className
        )}
      >
        <div className="flex items-start justify-between pb-4 border-b border-claude-hairline/60 dark:border-claude-surface-dark-soft">
          <div>
            <h3 className="font-serif text-xl font-normal tracking-serif-sm text-claude-ink dark:text-claude-on-dark">
              {title}
            </h3>
            {description && (
              <p className="mt-1 text-sm text-claude-muted dark:text-claude-on-dark-soft leading-normal">
                {description}
              </p>
            )}
          </div>
          <button
            onClick={onClose}
            className="h-8 w-8 rounded-full flex items-center justify-center text-claude-muted hover:text-claude-ink dark:text-claude-on-dark-soft dark:hover:text-claude-on-dark hover:bg-claude-surface-card/60 dark:hover:bg-claude-surface-dark-soft transition-colors"
            title="Close dialog (Esc)"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="pt-4">{children}</div>
      </div>
    </div>
  );
}
