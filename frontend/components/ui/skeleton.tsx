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
        "animate-pulse rounded-lg bg-[#9BA8AB]/50 dark:bg-[#253745]/80",
        className
      )}
      {...props}
    />
  );
}
