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
          <div className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400 dark:text-slate-500 pointer-events-none">
            {startIcon}
          </div>
        )}
        <input
          ref={ref}
          disabled={disabled}
          className={cn(
            "w-full rounded-xl bg-white dark:bg-navy-900 border border-slate-300 dark:border-navy-750 px-3.5 py-2.5 text-sm text-slate-900 dark:text-slate-100 placeholder:text-slate-400 dark:placeholder:text-slate-500 shadow-sm focus:border-cyan-500 focus:outline-none focus:ring-2 focus:ring-cyan-500/20 transition-all disabled:opacity-50 disabled:cursor-not-allowed",
            startIcon && "pl-10",
            endIcon && "pr-10",
            error && "border-red-500 focus:border-red-500 focus:ring-red-500/20",
            className
          )}
          {...props}
        />
        {endIcon && (
          <div className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 dark:text-slate-500">
            {endIcon}
          </div>
        )}
        {error && <p className="mt-1.5 text-xs text-red-500">{error}</p>}
      </div>
    );
  }
);

Input.displayName = "Input";

