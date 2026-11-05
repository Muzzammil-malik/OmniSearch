"use client";

import React, { useEffect, useState } from "react";
import {
  Search,
  FolderOpen,
  Cpu,
  Settings,
  Sun,
  Moon,
} from "lucide-react";
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

  const navItems = [
    { id: "search" as ActiveTab, label: "Search", icon: Search },
    { id: "library" as ActiveTab, label: "Library", icon: FolderOpen },
    {
      id: "indexing" as ActiveTab,
      label: "Indexing",
      icon: Cpu,
      hasPulse: isIndexingActive,
    },
    { id: "settings" as ActiveTab, label: "Settings", icon: Settings },
  ];

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-slate-50 dark:bg-navy-950 text-slate-900 dark:text-slate-100 font-sans">
      {/* Desktop Sidebar */}
      <aside className="hidden md:flex flex-col w-64 border-r border-slate-200 dark:border-navy-800 bg-white/70 dark:bg-navy-900/60 backdrop-blur-md z-30 select-none">
        {/* Brand Header */}
        <div className="p-5 flex items-center justify-between border-b border-slate-200/80 dark:border-navy-800/80">
          <div
            onClick={() => onTabChange("search")}
            className="flex items-center gap-3 cursor-pointer group"
          >
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-cyan-500 to-cyan-700 flex items-center justify-center text-slate-950 font-bold shadow-md shadow-cyan-500/20 group-hover:scale-105 transition-transform">
              <span className="text-base tracking-tight font-mono">Ω</span>
            </div>
            <div>
              <span className="font-semibold text-base tracking-tight block text-slate-900 dark:text-white">
                OmniSearch
              </span>
              <span className="text-[11px] text-slate-500 dark:text-slate-400 block -mt-0.5">
                Local Intelligence
              </span>
            </div>
          </div>
        </div>

        {/* Navigation Items */}
        <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => onTabChange(item.id)}
                className={cn(
                  "w-full flex items-center justify-between px-3.5 py-2.5 rounded-xl text-sm font-medium transition-all group",
                  isActive
                    ? "bg-cyan-500/10 text-cyan-600 dark:text-cyan-400 font-semibold"
                    : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200 hover:bg-slate-100/80 dark:hover:bg-navy-800/60"
                )}
              >
                <div className="flex items-center gap-3">
                  <Icon
                    className={cn(
                      "w-4 h-4 transition-colors",
                      isActive
                        ? "text-cyan-600 dark:text-cyan-400"
                        : "text-slate-400 dark:text-slate-500 group-hover:text-slate-700 dark:group-hover:text-slate-300"
                    )}
                  />
                  <span>{item.label}</span>
                </div>

                {item.hasPulse && (
                  <span className="flex h-2 w-2 relative">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-cyan-400 opacity-75" />
                    <span className="relative inline-flex rounded-full h-2 w-2 bg-cyan-500" />
                  </span>
                )}
              </button>
            );
          })}
        </nav>

        {/* Footer / System Status Card */}
        <div className="p-3 border-t border-slate-200/80 dark:border-navy-800/80 space-y-2">
          {/* System status pill */}
          <div
            onClick={() => onTabChange("settings")}
            className="flex items-center justify-between px-3 py-2 rounded-xl bg-slate-100/80 dark:bg-navy-850/80 border border-slate-200 dark:border-navy-750 cursor-pointer hover:border-cyan-500/30 transition-all text-xs"
          >
            <div className="flex items-center gap-2">
              {statusState === "healthy" && (
                <span className="w-2 h-2 rounded-full bg-emerald-500 shadow-sm shadow-emerald-500/50" />
              )}
              {statusState === "degraded" && (
                <span className="w-2 h-2 rounded-full bg-amber-500 animate-pulse" />
              )}
              {statusState === "offline" && (
                <span className="w-2 h-2 rounded-full bg-red-500" />
              )}
              <span className="font-medium text-slate-700 dark:text-slate-300 capitalize">
                {statusState === "healthy"
                  ? "System Ready"
                  : statusState === "degraded"
                  ? "Degraded"
                  : "Backend Offline"}
              </span>
            </div>
            <span className="font-mono text-[10px] text-slate-400 dark:text-slate-500">
              v0.1.0
            </span>
          </div>

          {/* Quick theme switch */}
          <div className="flex items-center justify-between px-2 pt-1 text-xs text-slate-500 dark:text-slate-400">
            <span>Appearance</span>
            <button
              onClick={() => setTheme(resolvedTheme === "dark" ? "light" : "dark")}
              className="p-1.5 rounded-lg hover:bg-slate-200/60 dark:hover:bg-navy-800 text-slate-600 dark:text-slate-400 transition-colors"
              title="Toggle theme"
            >
              {resolvedTheme === "dark" ? (
                <Sun className="w-4 h-4 text-amber-400" />
              ) : (
                <Moon className="w-4 h-4 text-cyan-600" />
              )}
            </button>
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0 h-full overflow-hidden">
        {/* Mobile Top Header */}
        <header className="md:hidden flex items-center justify-between px-4 py-3 border-b border-slate-200 dark:border-navy-800 bg-white/80 dark:bg-navy-900/80 backdrop-blur-md z-30">
          <div
            onClick={() => onTabChange("search")}
            className="flex items-center gap-2.5 cursor-pointer"
          >
            <div className="w-7 h-7 rounded-lg bg-cyan-500 flex items-center justify-center text-slate-950 font-bold text-xs">
              Ω
            </div>
            <span className="font-semibold text-sm tracking-tight text-slate-900 dark:text-white">
              OmniSearch
            </span>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setTheme(resolvedTheme === "dark" ? "light" : "dark")}
              className="p-2 rounded-lg text-slate-500 dark:text-slate-400"
            >
              {resolvedTheme === "dark" ? (
                <Sun className="w-4 h-4 text-amber-400" />
              ) : (
                <Moon className="w-4 h-4 text-cyan-600" />
              )}
            </button>
          </div>
        </header>

        {/* Scrollable View Container */}
        <main className="flex-1 overflow-y-auto overflow-x-hidden relative">
          {children}
        </main>

        {/* Mobile Bottom Navigation Bar */}
        <nav className="md:hidden flex items-center justify-around py-2 border-t border-slate-200 dark:border-navy-800 bg-white/95 dark:bg-navy-900/95 backdrop-blur-md z-30">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => onTabChange(item.id)}
                className={cn(
                  "flex flex-col items-center gap-1 py-1 px-3 rounded-lg text-xs transition-colors relative",
                  isActive
                    ? "text-cyan-600 dark:text-cyan-400 font-semibold"
                    : "text-slate-500 dark:text-slate-400"
                )}
              >
                <Icon className="w-5 h-5" />
                <span className="text-[10px]">{item.label}</span>
                {item.hasPulse && (
                  <span className="absolute top-1 right-3 flex h-2 w-2">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-cyan-400 opacity-75" />
                    <span className="relative inline-flex rounded-full h-2 w-2 bg-cyan-500" />
                  </span>
                )}
              </button>
            );
          })}
        </nav>
      </div>
    </div>
  );
}
