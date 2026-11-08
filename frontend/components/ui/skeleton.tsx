"use client";

import React from "react";
import { cn } from "@/lib/utils";

export function Skeleton({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "animate-pulse rounded-md bg-claude-hairline/35 dark:bg-claude-surface-dark-soft/60",
        className
      )}
      {...props}
    />
  );
}
