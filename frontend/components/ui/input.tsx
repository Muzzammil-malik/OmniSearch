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
          <div className="absolute left-3.5 top-1/2 -translate-y-1/2 text-[#4A5C6A] dark:text-[#9BA8AB] pointer-events-none">
            {startIcon}
          </div>
        )}
        <input
          ref={ref}
          disabled={disabled}
          className={cn(
            "w-full rounded-xl bg-[#E2E6E5] dark:bg-[#06141B] border border-[#9BA8AB] dark:border-[#4A5C6A] px-3.5 py-2.5 text-sm text-[#06141B] dark:text-[#CCD0CF] placeholder:text-[#4A5C6A] dark:placeholder:text-[#4A5C6A] focus:border-[#06141B] dark:focus:border-[#9BA8AB] focus:outline-none focus:ring-1 focus:ring-[#11212D]/30 dark:focus:ring-[#9BA8AB]/30 transition-colors duration-150 disabled:opacity-50 disabled:cursor-not-allowed",
            startIcon && "pl-10",
            endIcon && "pr-10",
            error && "border-[#9b2226] focus:border-[#9b2226] focus:ring-[#9b2226]/20",
            className
          )}
          {...props}
        />
        {endIcon && (
          <div className="absolute right-3 top-1/2 -translate-y-1/2 text-[#4A5C6A] dark:text-[#9BA8AB]">
            {endIcon}
          </div>
        )}
        {error && (
          <p className="mt-1.5 text-xs text-[#9b2226] dark:text-[#f2b8b5]">{error}</p>
        )}
      </div>
    );
  }
);

Input.displayName = "Input";
