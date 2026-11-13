"use client";

import React, { useEffect, useState } from "react";
import Image from "next/image";
import {
  Search,
  FolderOpen,
  Layers,
  SlidersHorizontal,
  Sun,
  Moon,
  PanelLeftOpen,
  PanelLeftClose,
} from "lucide-react";
import { motion, AnimatePresence, useReducedMotion } from "framer-motion";
import { useTheme } from "./theme-provider";
import { systemApi } from "@/lib/api";
import { cn } from "@/lib/utils";

export type ActiveTab = "search" | "library" | "indexing" | "settings";

interface AppShellProps {
  activeTab: ActiveTab;
  onTabChange: (tab: ActiveTab) => void;
  children: React.ReactNode;
  isIndexingActive?: boolean;
}

export function AppShell({
  activeTab,
  onTabChange,
  children,
  isIndexingActive = false,
}: AppShellProps) {
  const { resolvedTheme, setTheme } = useTheme();
  const prefersReducedMotion = useReducedMotion();

  const [isExpanded, setIsExpanded] = useState(false);
  const [isBrandHovered, setIsBrandHovered] = useState(false);
  const [statusState, setStatusState] = useState<"healthy" | "degraded" | "offline">("healthy");

  useEffect(() => {
    let isMounted = true;
    const fetchStatus = async () => {
      try {
        const res = await systemApi.getStatus();
        if (!isMounted) return;
        setStatusState(res.status === "healthy" ? "healthy" : "degraded");
      } catch {
        if (!isMounted) return;
        setStatusState("offline");
      }
    };

    fetchStatus();
    const interval = setInterval(fetchStatus, 15000);
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, []);

  const navItems: {
    id: ActiveTab;
    label: string;
    icon: React.ComponentType<{ className?: string }>;
    isLive?: boolean;
  }[] = [
    { id: "search", label: "Search", icon: Search },
    { id: "library", label: "Library", icon: FolderOpen },
    {
      id: "indexing",
      label: "Indexing",
      icon: Layers,
      isLive: isIndexingActive,
    },
    { id: "settings", label: "Settings", icon: SlidersHorizontal },
  ];

  const statusLabel =
    statusState === "healthy"
      ? "System Ready"
      : statusState === "degraded"
      ? "System Degraded"
      : "Backend Offline";

  const sidebarTransition = prefersReducedMotion
    ? { duration: 0 }
    : { duration: 0.22, ease: [0.16, 1, 0.3, 1] as const };

  return (
    <div className="flex flex-col md:flex-row h-screen w-screen overflow-hidden bg-[#BFC5C4] dark:bg-[#06141B] text-[#06141B] dark:text-[#CCD0CF] font-sans select-none">
      {/* ================================================================== */}
      {/* DESKTOP / TABLET FLOATING THEME-AWARE VERTICAL NAVIGATION RAIL     */}
      {/* ================================================================== */}
      <div className="hidden md:flex h-full shrink-0 py-4 pl-4 pr-2 lg:py-5 lg:pl-6 lg:pr-2.5 z-30">
        <motion.aside
          initial={false}
          animate={{ width: isExpanded ? 216 : 64 }}
          transition={sidebarTransition}
          aria-label="Application navigation"
          className="flex flex-col justify-between h-full rounded-[28px] lg:rounded-[32px] bg-[var(--sidebar-background)] text-[var(--sidebar-text-primary)] border border-[var(--sidebar-border)] shadow-card py-4 px-2.5 overflow-hidden transition-colors duration-200"
        >
          {/* Top Section: Brand Area + Primary Navigation Icons */}
          <div className="flex flex-col gap-6">
            {/* Logo / Brand Area with Hover-to-Reveal Sidebar Toggle */}
            <div
              onMouseEnter={() => setIsBrandHovered(true)}
              onMouseLeave={() => setIsBrandHovered(false)}
              className="relative flex items-center h-10 px-0.5"
            >
              {isExpanded ? (
                <div className="flex items-center justify-between w-full gap-1.5">
                  <button
                    type="button"
                    onClick={() => onTabChange("search")}
                    className="flex items-center gap-2.5 px-1.5 py-1 rounded-full text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--sidebar-ring)] transition-opacity hover:opacity-90 min-w-0"
                    title="OmniSearch — Go to Search"
                  >
                    <span className="w-7 h-7 rounded-full bg-[var(--sidebar-brand-bg)] border border-[var(--sidebar-brand-border)] flex items-center justify-center shrink-0 overflow-hidden transition-colors duration-200 p-0.5">
                      <Image
                        src="/assets/OmniSearch_Logo.png"
                        alt="OmniSearch logo"
                        width={24}
                        height={24}
                        priority
                        className="w-full h-full object-contain"
                      />
                    </span>
                    <motion.span
                      initial={{ opacity: 0, x: -4 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={sidebarTransition}
                      className="font-serif text-[16px] font-medium tracking-tight text-[var(--sidebar-text-primary)] truncate transition-colors duration-200"
                    >
                      OmniSearch
                    </motion.span>
                  </button>

                  <button
                    type="button"
                    onClick={() => setIsExpanded(false)}
                    aria-label="Collapse navigation sidebar"
                    title="Collapse sidebar"
                    className={cn(
                      "inline-flex items-center justify-center h-8 w-8 rounded-full text-[var(--sidebar-text-muted)] hover:text-[var(--sidebar-text-primary)] hover:bg-[var(--sidebar-hover-bg)] transition-all duration-150 shrink-0 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--sidebar-ring)]",
                      isBrandHovered ? "opacity-100" : "opacity-60 hover:opacity-100 focus-visible:opacity-100"
                    )}
                  >
                    <PanelLeftClose className="w-4 h-4 stroke-[1.75]" />
                  </button>
                </div>
              ) : (
                <div className="relative flex items-center justify-center w-full">
                  {/* Default Collapsed Brand Mark; on hover reveals the Expand toggle */}
                  <button
                    type="button"
                    onClick={() => setIsExpanded(true)}
                    aria-label="Expand navigation sidebar"
                    title="Expand sidebar"
                    className="group relative flex items-center justify-center w-10 h-10 rounded-full bg-[var(--sidebar-brand-bg)] border border-[var(--sidebar-brand-border)] hover:bg-[var(--sidebar-brand-hover-bg)] text-[var(--sidebar-text-primary)] transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--sidebar-ring)]"
                  >
                    <span
                      className={cn(
                        "w-6 h-6 flex items-center justify-center transition-all duration-150 p-0.5",
                        isBrandHovered
                          ? "opacity-0 scale-90"
                          : "opacity-100 scale-100 group-focus-visible:opacity-0"
                      )}
                    >
                      <Image
                        src="/assets/OmniSearch_Logo.png"
                        alt="OmniSearch logo"
                        width={24}
                        height={24}
                        priority
                        className="w-full h-full object-contain"
                      />
                    </span>
                    <PanelLeftOpen
                      className={cn(
                        "w-4 h-4 stroke-[1.75] absolute transition-all duration-150",
                        isBrandHovered
                          ? "opacity-100 scale-100"
                          : "opacity-0 scale-90 group-focus-visible:opacity-100 group-focus-visible:scale-100"
                      )}
                    />
                  </button>
                </div>
              )}
            </div>

            {/* Primary Navigation Items */}
            <nav aria-label="Primary" className="flex flex-col gap-1.5">
              {navItems.map((item) => {
                const Icon = item.icon;
                const isActive = activeTab === item.id;

                return (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => onTabChange(item.id)}
                    aria-label={item.label}
                    aria-current={isActive ? "page" : undefined}
                    title={!isExpanded ? item.label : undefined}
                    className={cn(
                      "relative flex items-center h-10 rounded-full text-xs font-medium transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--sidebar-ring)]",
                      isExpanded ? "px-3.5 justify-start gap-3 w-full" : "w-10 mx-auto justify-center",
                      isActive
                        ? "text-[var(--sidebar-active-text)]"
                        : "text-[var(--sidebar-text-muted)] hover:text-[var(--sidebar-text-primary)] hover:bg-[var(--sidebar-hover-bg)]"
                    )}
                  >
                    {isActive && (
                      <motion.span
                        layoutId="rail-active-pill"
                        transition={sidebarTransition}
                        className="absolute inset-0 rounded-full bg-[var(--sidebar-active-bg)] border border-[var(--sidebar-active-border)] transition-colors duration-200"
                      />
                    )}

                    <span className="relative z-10 flex items-center justify-center shrink-0">
                      <Icon className="w-4 h-4 stroke-[1.75]" />
                      {!isExpanded && item.isLive && (
                        <span className="absolute -top-0.5 -right-0.5 w-1.5 h-1.5 rounded-full bg-[var(--sidebar-status-healthy)]" />
                      )}
                    </span>

                    <AnimatePresence initial={false}>
                      {isExpanded && (
                        <motion.span
                          initial={{ opacity: 0, x: -4 }}
                          animate={{ opacity: 1, x: 0 }}
                          exit={{ opacity: 0, x: -4 }}
                          transition={{ duration: prefersReducedMotion ? 0 : 0.16, ease: [0.16, 1, 0.3, 1] }}
                          className="relative z-10 flex items-center justify-between flex-1 min-w-0 whitespace-nowrap"
                        >
                          <span className="truncate">{item.label}</span>
                          {item.isLive && (
                            <span
                              className={cn(
                                "text-[10px] font-mono",
                                isActive
                                  ? "text-[var(--sidebar-active-text)] opacity-80"
                                  : "text-[var(--sidebar-text-muted)]"
                              )}
                            >
                              Active
                            </span>
                          )}
                        </motion.span>
                      )}
                    </AnimatePresence>
                  </button>
                );
              })}
            </nav>
          </div>

          {/* Bottom Section: Theme Control & Backend Status */}
          <div className="flex flex-col gap-1.5 pt-3.5 border-t border-[var(--sidebar-divider)] transition-colors duration-200">
            {/* Theme Toggle */}
            <button
              type="button"
              onClick={() => setTheme(resolvedTheme === "dark" ? "light" : "dark")}
              aria-label={
                resolvedTheme === "dark"
                  ? "Switch to Light mode"
                  : "Switch to Dark mode"
              }
              title={
                !isExpanded
                  ? resolvedTheme === "dark"
                    ? "Switch to Light mode"
                    : "Switch to Dark mode"
                  : undefined
              }
              className={cn(
                "flex items-center h-9 rounded-full text-xs font-medium text-[var(--sidebar-text-muted)] hover:text-[var(--sidebar-text-primary)] hover:bg-[var(--sidebar-hover-bg)] transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--sidebar-ring)]",
                isExpanded ? "px-3.5 justify-start gap-3 w-full" : "w-10 mx-auto justify-center"
              )}
            >
              {resolvedTheme === "dark" ? (
                <Sun className="w-4 h-4 stroke-[1.75] shrink-0" />
              ) : (
                <Moon className="w-4 h-4 stroke-[1.75] shrink-0" />
              )}
              <AnimatePresence initial={false}>
                {isExpanded && (
                  <motion.span
                    initial={{ opacity: 0, x: -4 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: -4 }}
                    transition={{ duration: prefersReducedMotion ? 0 : 0.16 }}
                    className="truncate whitespace-nowrap"
                  >
                    {resolvedTheme === "dark" ? "Light appearance" : "Dark appearance"}
                  </motion.span>
                )}
              </AnimatePresence>
            </button>

            {/* Backend Status Indicator */}
            <button
              type="button"
              onClick={() => onTabChange("settings")}
              aria-label={`Backend status: ${statusLabel}. Open Settings.`}
              title={!isExpanded ? `${statusLabel} — Click to inspect` : "Inspect system diagnostics"}
              className={cn(
                "flex items-center h-9 rounded-full text-xs font-medium text-[var(--sidebar-text-muted)] hover:text-[var(--sidebar-text-primary)] hover:bg-[var(--sidebar-hover-bg)] transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--sidebar-ring)]",
                isExpanded ? "px-3.5 justify-start gap-3 w-full" : "w-10 mx-auto justify-center"
              )}
            >
              <span className="flex items-center justify-center w-4 h-4 shrink-0">
                <span
                  className={cn(
                    "w-2 h-2 rounded-full transition-colors duration-200",
                    statusState === "healthy"
                      ? "bg-[var(--sidebar-status-healthy)]"
                      : statusState === "degraded"
                      ? "bg-[var(--sidebar-status-degraded)]"
                      : "bg-[var(--sidebar-status-offline)]"
                  )}
                />
              </span>
              <AnimatePresence initial={false}>
                {isExpanded && (
                  <motion.span
                    initial={{ opacity: 0, x: -4 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: -4 }}
                    transition={{ duration: prefersReducedMotion ? 0 : 0.16 }}
                    className="truncate whitespace-nowrap text-[11px]"
                  >
                    {statusLabel}
                  </motion.span>
                )}
              </AnimatePresence>
            </button>
          </div>
        </motion.aside>
      </div>

      {/* ================================================================== */}
      {/* MOBILE HEADER (Only on narrow < md viewports)                      */}
      {/* ================================================================== */}
      <header className="md:hidden flex items-center justify-between px-4 pt-3 pb-1 shrink-0">
        <button
          type="button"
          onClick={() => onTabChange("search")}
          className="flex items-center gap-2 rounded-full px-2 py-1 -ml-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#4A5C6A]"
        >
          <span className="w-6 h-6 rounded-full bg-[#11212D] dark:bg-[#253745] flex items-center justify-center shrink-0 overflow-hidden p-0.5">
            <Image
              src="/assets/OmniSearch_Logo.png"
              alt="OmniSearch logo"
              width={20}
              height={20}
              priority
              className="w-full h-full object-contain"
            />
          </span>
          <span className="font-serif text-base font-medium text-[#06141B] dark:text-[#CCD0CF]">
            OmniSearch
          </span>
        </button>

        <div className="flex items-center gap-1.5">
          <button
            type="button"
            onClick={() => onTabChange("settings")}
            aria-label={`Backend status: ${statusLabel}`}
            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] bg-[#D8DCDB] dark:bg-[#11212D] border border-[#9BA8AB] dark:border-[#253745] text-[#253745] dark:text-[#9BA8AB]"
          >
            <span
              className={cn(
                "w-1.5 h-1.5 rounded-full",
                statusState === "healthy"
                  ? "bg-[#2d6a4f] dark:bg-[#74c69d]"
                  : statusState === "degraded"
                  ? "bg-[#b5651d] dark:bg-[#fcd34d]"
                  : "bg-[#9b2226] dark:bg-[#f2b8b5]"
              )}
            />
            <span>{statusState === "healthy" ? "Ready" : statusState}</span>
          </button>

          <button
            type="button"
            onClick={() => setTheme(resolvedTheme === "dark" ? "light" : "dark")}
            aria-label="Toggle color theme"
            className="inline-flex items-center justify-center h-7 w-7 rounded-full bg-[#D8DCDB] dark:bg-[#11212D] border border-[#9BA8AB] dark:border-[#253745] text-[#253745] dark:text-[#9BA8AB]"
          >
            {resolvedTheme === "dark" ? (
              <Sun className="w-3.5 h-3.5" />
            ) : (
              <Moon className="w-3.5 h-3.5" />
            )}
          </button>
        </div>
      </header>

      {/* ================================================================== */}
      {/* FLOATING MAIN WORKSPACE CANVAS                                     */}
      {/* ================================================================== */}
      <div className="flex-1 flex flex-col min-w-0 min-h-0 p-2 sm:p-3.5 md:py-4 md:pr-4 md:pl-1 lg:py-5 lg:pr-6 lg:pl-2">
        <div className="relative flex-1 flex flex-col w-full h-full rounded-[24px] sm:rounded-[28px] lg:rounded-[32px] bg-[#CCD0CF] dark:bg-[#11212D] border border-[#9BA8AB] dark:border-[#253745] shadow-card overflow-hidden select-text">
          <main className="flex-1 overflow-y-auto overflow-x-hidden relative h-full">
            <AnimatePresence mode="wait" initial={false}>
              <motion.div
                key={activeTab}
                initial={prefersReducedMotion ? { opacity: 1 } : { opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={prefersReducedMotion ? { opacity: 1 } : { opacity: 0 }}
                transition={{ duration: prefersReducedMotion ? 0 : 0.2, ease: [0.16, 1, 0.3, 1] }}
                className="h-full"
              >
                {children}
              </motion.div>
            </AnimatePresence>
          </main>
        </div>
      </div>

      {/* ================================================================== */}
      {/* MOBILE NAVIGATION BAR (Only on narrow < md viewports)              */}
      {/* ================================================================== */}
      <nav
        aria-label="Mobile navigation"
        className="md:hidden shrink-0 px-3 pb-2.5 pt-1 z-30"
      >
        <div className="flex items-center justify-around gap-1 p-1 rounded-full bg-[#D8DCDB] dark:bg-[#11212D] border border-[#9BA8AB] dark:border-[#253745]">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => onTabChange(item.id)}
                className={cn(
                  "flex-1 flex items-center justify-center gap-1.5 py-1.5 px-2.5 rounded-full text-xs font-medium transition-colors whitespace-nowrap",
                  isActive
                    ? "bg-[#06141B] text-[#CCD0CF] dark:bg-[#CCD0CF] dark:text-[#06141B]"
                    : "text-[#253745] dark:text-[#9BA8AB]"
                )}
              >
                <Icon className="w-3.5 h-3.5" />
                <span>{item.label}</span>
              </button>
            );
          })}
        </div>
      </nav>
    </div>
  );
}
