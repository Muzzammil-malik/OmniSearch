"use client";

import React from "react";
import { cn } from "@/lib/utils";

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: "default" | "cyan" | "green" | "amber" | "red" | "purple" | "outline";
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
    sm: "text-[10px] px-1.5 py-0.5 rounded font-mono font-medium leading-none",
    md: "text-xs px-2.5 py-0.5 rounded-full font-medium leading-normal",
  }[size];

  const variantClasses = {
    default:
      "bg-slate-200 text-slate-800 dark:bg-navy-800 dark:text-slate-300 border border-slate-300/80 dark:border-navy-700",
    cyan: "bg-cyan-500/10 text-cyan-600 dark:text-cyan-400 border border-cyan-500/20",
    green: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20",
    amber: "bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20",
    red: "bg-red-500/10 text-red-600 dark:text-red-400 border border-red-500/20",
    purple: "bg-purple-500/10 text-purple-600 dark:text-purple-400 border border-purple-500/20",
    outline: "bg-transparent text-slate-600 dark:text-slate-400 border border-slate-300 dark:border-navy-700",
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

