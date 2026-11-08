"use client";

import React from "react";
import { cn } from "@/lib/utils";

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: "default" | "cyan" | "green" | "amber" | "red" | "purple" | "outline" | "slate";
  size?: "sm" | "md";
}

export function Badge({
  className,
  variant = "default",
  size = "md",
  children,
  ...props
}: BadgeProps) {
  const sizeClasses = {
    sm: "text-[11px] px-2 py-0.5 rounded-sm font-mono leading-none",
    md: "text-xs px-3 py-1 rounded-pill font-medium leading-normal",
  }[size];

  const variantClasses = {
    default:
      "bg-claude-surface-card/60 text-claude-ink dark:bg-claude-surface-dark-soft dark:text-claude-on-dark border border-claude-hairline dark:border-claude-muted/30",
    slate:
      "bg-claude-primary text-claude-on-primary dark:bg-claude-on-dark dark:text-claude-ink font-medium tracking-caption-wide uppercase",
    cyan:
      "bg-claude-muted/15 text-claude-muted dark:bg-claude-muted/25 dark:text-claude-on-dark border border-claude-muted/20",
    green:
      "bg-emerald-600/10 text-emerald-800 dark:text-emerald-400 border border-emerald-600/20",
    amber:
      "bg-amber-600/10 text-amber-800 dark:text-amber-400 border border-amber-600/20",
    red:
      "bg-claude-error/10 text-red-700 dark:text-red-400 border border-claude-error/20",
    purple:
      "bg-claude-primary/10 text-claude-primary dark:bg-claude-primary-active/40 dark:text-claude-on-dark border border-claude-primary/20",
    outline:
      "bg-transparent text-claude-muted dark:text-claude-on-dark-soft border border-claude-hairline dark:border-claude-surface-dark-soft",
  }[variant];

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 select-none whitespace-nowrap",
        sizeClasses,
        variantClasses,
        className
      )}
      {...props}
    >
      {children}
    </span>
  );
}
