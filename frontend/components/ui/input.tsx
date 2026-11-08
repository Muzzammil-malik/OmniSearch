"use client";

import React, { forwardRef } from "react";
import { cn } from "@/lib/utils";

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  error?: string;
  startIcon?: React.ReactNode;
  endIcon?: React.ReactNode;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, error, startIcon, endIcon, disabled, ...props }, ref) => {
    return (
      <div className="relative w-full">
        {startIcon && (
          <div className="absolute left-3.5 top-1/2 -translate-y-1/2 text-claude-muted dark:text-claude-on-dark-soft pointer-events-none">
            {startIcon}
          </div>
        )}
        <input
          ref={ref}
          disabled={disabled}
          className={cn(
            "w-full h-10 rounded-md bg-claude-canvas dark:bg-claude-surface-dark-elevated border border-claude-hairline dark:border-claude-surface-dark-soft px-3.5 py-2.5 text-sm text-claude-ink dark:text-claude-on-dark placeholder:text-claude-muted dark:placeholder:text-claude-muted shadow-subtle focus:border-claude-primary dark:focus:border-claude-on-dark focus:outline-none focus:ring-3 focus:ring-claude-primary/15 dark:focus:ring-claude-on-dark/15 transition-all disabled:opacity-50 disabled:cursor-not-allowed",
            startIcon && "pl-10",
            endIcon && "pr-10",
            error && "border-claude-error focus:border-claude-error focus:ring-claude-error/20",
            className
          )}
          {...props}
        />
        {endIcon && (
          <div className="absolute right-3.5 top-1/2 -translate-y-1/2 text-claude-muted dark:text-claude-on-dark-soft">
            {endIcon}
          </div>
        )}
        {error && <p className="mt-1.5 text-xs text-claude-error font-medium">{error}</p>}
      </div>
    );
  }
);

Input.displayName = "Input";
