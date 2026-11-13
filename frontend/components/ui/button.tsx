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
      xs: "text-[11px] font-medium px-3 py-1 rounded-full h-7 gap-1.5",
      sm: "text-xs font-medium px-3.5 py-1.5 rounded-full h-8 gap-1.5",
      md: "text-xs font-medium px-4 py-2 rounded-full h-9 gap-2",
      lg: "text-sm font-medium px-5 py-2.5 rounded-full h-10 gap-2",
      icon: "p-2 rounded-full h-8 w-8 justify-center items-center",
    }[size];

    const variantClasses = {
      primary:
        "bg-[#06141B] hover:bg-[#11212D] text-[#CCD0CF] dark:bg-[#CCD0CF] dark:hover:bg-[#9BA8AB] dark:text-[#06141B] border border-transparent shadow-subtle",
      secondary:
        "bg-[#9BA8AB]/35 hover:bg-[#9BA8AB]/55 text-[#06141B] border border-[#4A5C6A]/50 dark:bg-[#253745] dark:hover:bg-[#4A5C6A] dark:text-[#CCD0CF] dark:border-[#4A5C6A]",
      ghost:
        "bg-transparent text-[#253745] hover:text-[#06141B] hover:bg-[#06141B]/[0.07] dark:text-[#9BA8AB] dark:hover:text-[#CCD0CF] dark:hover:bg-[#253745]/70",
      outline:
        "bg-transparent border border-[#4A5C6A]/60 dark:border-[#4A5C6A] text-[#06141B] dark:text-[#CCD0CF] hover:bg-[#06141B]/[0.06] dark:hover:bg-[#253745]/60",
      danger:
        "bg-[#9b2226]/[0.08] hover:bg-[#9b2226]/[0.15] text-[#9b2226] dark:bg-[#9b2226]/20 dark:hover:bg-[#9b2226]/30 dark:text-[#f2b8b5] border border-[#9b2226]/25",
    }[variant];

    return (
      <button
        ref={ref}
        disabled={disabled || isLoading}
        className={cn(
          "inline-flex items-center justify-center whitespace-nowrap shrink-0 transition-colors duration-150 ease-editorial select-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#4A5C6A] focus-visible:ring-offset-1 focus-visible:ring-offset-[#CCD0CF] dark:focus-visible:ring-[#9BA8AB] dark:focus-visible:ring-offset-[#06141B] disabled:opacity-45 disabled:pointer-events-none disabled:cursor-not-allowed",
          sizeClasses,
          variantClasses,
          className
        )}
        {...props}
      >
        {isLoading && (
          <svg
            className="animate-spin -ml-0.5 h-3.5 w-3.5 text-current"
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
              strokeWidth="2.5"
            />
            <path
              className="opacity-80"
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
