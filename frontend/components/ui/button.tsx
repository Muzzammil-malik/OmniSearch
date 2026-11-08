"use client";

import React, { forwardRef } from "react";
import { cn } from "@/lib/utils";

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "ghost" | "danger" | "outline";
  size?: "xs" | "sm" | "md" | "lg" | "icon";
  isLoading?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      className,
      variant = "secondary",
      size = "md",
      isLoading = false,
      disabled,
      children,
      ...props
    },
    ref
  ) => {
    const sizeClasses = {
      xs: "text-xs px-2.5 py-1 rounded-sm h-7 gap-1.5",
      sm: "text-xs font-medium px-3 py-1.5 rounded-sm h-8 gap-2",
      md: "text-sm font-medium px-4 py-2 rounded-md h-10 gap-2",
      lg: "text-sm font-medium px-5 py-2.5 rounded-lg h-11 gap-2.5",
      icon: "h-9 w-9 rounded-full justify-center items-center p-0",
    }[size];

    const variantClasses = {
      primary:
        "bg-claude-primary hover:bg-claude-primary-active text-claude-on-primary font-medium shadow-subtle active:bg-claude-primary-active dark:bg-claude-on-dark dark:hover:bg-claude-on-dark-soft dark:text-claude-ink transition-all",
      secondary:
        "bg-claude-canvas hover:bg-claude-surface-card text-claude-ink dark:bg-claude-surface-dark-elevated dark:hover:bg-claude-surface-dark-soft dark:text-claude-on-dark border border-claude-hairline dark:border-claude-surface-dark-soft active:scale-[0.99] transition-all",
      ghost:
        "text-claude-ink hover:bg-claude-surface-card/60 dark:text-claude-on-dark dark:hover:bg-claude-surface-dark-elevated/70 active:scale-[0.99] transition-all",
      outline:
        "bg-transparent border border-claude-hairline dark:border-claude-surface-dark-soft text-claude-ink dark:text-claude-on-dark hover:bg-claude-surface-card/40 dark:hover:bg-claude-surface-dark-elevated/50 active:scale-[0.99] transition-all",
      danger:
        "bg-claude-error/10 hover:bg-claude-error/20 text-claude-error border border-claude-error/30 active:scale-[0.99] transition-all",
    }[variant];

    return (
      <button
        ref={ref}
        disabled={disabled || isLoading}
        className={cn(
          "inline-flex items-center justify-center select-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-claude-primary/30 dark:focus-visible:ring-claude-on-dark/30 disabled:opacity-50 disabled:pointer-events-none disabled:cursor-not-allowed",
          sizeClasses,
          variantClasses,
          className
        )}
        {...props}
      >
        {isLoading && (
          <svg
            className="animate-spin -ml-0.5 h-4 w-4 text-current"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
          >
            <circle
              className="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              strokeWidth="3"
            />
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
            />
          </svg>
        )}
        {children}
      </button>
    );
  }
);

Button.displayName = "Button";
