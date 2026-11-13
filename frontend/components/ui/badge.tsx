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
    md: "text-[11px] px-2 py-0.5 rounded-md font-medium leading-normal",
  }[size];

  const variantClasses = {
    default:
      "bg-[#9BA8AB]/35 text-[#06141B] dark:bg-[#253745] dark:text-[#CCD0CF] border border-[#4A5C6A]/50 dark:border-[#4A5C6A]",
    cyan:
      "bg-[#253745]/15 text-[#11212D] dark:bg-[#4A5C6A]/35 dark:text-[#CCD0CF] border border-[#253745]/30 dark:border-[#9BA8AB]/30",
    green:
      "bg-[#2d6a4f]/[0.1] text-[#1b4332] dark:bg-[#40916c]/20 dark:text-[#b7e4c7] border border-[#2d6a4f]/25",
    amber:
      "bg-[#b5651d]/[0.1] text-[#7f4f24] dark:bg-[#d97706]/20 dark:text-[#fcd34d] border border-[#b5651d]/25",
    red:
      "bg-[#9b2226]/[0.1] text-[#9b2226] dark:bg-[#9b2226]/20 dark:text-[#f2b8b5] border border-[#9b2226]/25",
    purple:
      "bg-[#4A5C6A]/20 text-[#253745] dark:bg-[#4A5C6A]/35 dark:text-[#9BA8AB] border border-[#4A5C6A]/35",
    outline:
      "bg-transparent text-[#253745] dark:text-[#9BA8AB] border border-[#4A5C6A]/60 dark:border-[#4A5C6A]",
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
