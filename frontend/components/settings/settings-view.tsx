"use client";

import React, { useEffect, useState } from "react";
import {
  Sun,
  Moon,
  Laptop,
  RotateCw,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { systemApi } from "@/lib/api";
import { SearchMode, SystemStatusResponse } from "@/lib/types";
import { cn, formatBytes, formatNumber } from "@/lib/utils";
import { useTheme } from "../theme-provider";
import { Button } from "../ui/button";

interface SettingsViewProps {
  defaultMode: SearchMode;
  onDefaultModeChange: (mode: SearchMode) => void;
  defaultLimit: number;
  onDefaultLimitChange: (limit: number) => void;
}

export function SettingsView({
  defaultMode,
  onDefaultModeChange,
  defaultLimit,
  onDefaultLimitChange,
}: SettingsViewProps) {
  const { theme, setTheme } = useTheme();
  const [systemStatus, setSystemStatus] = useState<SystemStatusResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isDiagnosticsOpen, setIsDiagnosticsOpen] = useState(true);

  const fetchStatus = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await systemApi.getStatus();
      setSystemStatus(res);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load system diagnostics");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchStatus();
  }, []);

  return (
    <div className="px-6 sm:px-10 py-8 sm:py-10 max-w-5xl mx-auto space-y-10 font-sans">
      {/* Top Editorial Header */}
      <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4 pb-6 border-b border-[#9BA8AB] dark:border-[#253745]">
        <div>
          <p className="text-[11px] font-mono uppercase tracking-widest text-[#4A5C6A] dark:text-[#9BA8AB] mb-1.5">
            Configuration & Diagnostics
          </p>
          <h1 className="text-2xl sm:text-3xl font-serif font-normal tracking-tight text-[#06141B] dark:text-[#CCD0CF]">
            Settings & System
          </h1>
          <p className="text-xs sm:text-sm text-[#253745] dark:text-[#9BA8AB] mt-1">
            Configure retrieval defaults, interface appearance, and local subsystem diagnostics.
          </p>
        </div>

        <Button variant="outline" size="sm" onClick={fetchStatus} disabled={isLoading}>
          <RotateCw className={`w-3.5 h-3.5 mr-1.5 ${isLoading ? "animate-spin" : ""}`} />
          Refresh status
        </Button>
      </div>

      {/* ==================================================================== */}
      {/* SECTION 1: PREFERENCES                                                */}
      {/* ==================================================================== */}
      <div className="space-y-6">
        <h2 className="text-[11px] font-mono uppercase tracking-widest text-[#4A5C6A] dark:text-[#9BA8AB]">
          Interface & Retrieval Preferences
        </h2>

        <div className="rounded-xl bg-[#D8DCDB] dark:bg-[#06141B]/55 border border-[#9BA8AB] dark:border-[#253745] divide-y divide-[#9BA8AB] dark:divide-[#253745]">
          {/* Appearance Row */}
          <div className="p-6 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <h3 className="text-base font-serif font-medium text-[#06141B] dark:text-[#CCD0CF]">
                Appearance
              </h3>
              <p className="text-xs text-[#253745] dark:text-[#9BA8AB] mt-0.5">
                Choose between the Deep Navy surface (#06141B), Silver Mist canvas (#CCD0CF), or system preference.
              </p>
            </div>

            {/* Pill-shaped theme selector buttons */}
            <div
              role="group"
              aria-label="Color theme preference"
              className="inline-flex items-center gap-1.5 p-1 rounded-full bg-[#CCD0CF] dark:bg-[#06141B] border border-[#9BA8AB] dark:border-[#253745] self-start sm:self-center"
            >
              <button
                type="button"
                onClick={() => setTheme("dark")}
                className={cn(
                  "inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-full text-xs font-medium transition-colors",
                  theme === "dark"
                    ? "bg-[#06141B] text-[#CCD0CF] dark:bg-[#CCD0CF] dark:text-[#06141B]"
                    : "text-[#253745] dark:text-[#9BA8AB] hover:text-[#06141B] dark:hover:text-[#CCD0CF]"
                )}
              >
                <Moon className="w-3.5 h-3.5" />
                <span>Dark</span>
              </button>

              <button
                type="button"
                onClick={() => setTheme("light")}
                className={cn(
                  "inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-full text-xs font-medium transition-colors",
                  theme === "light"
                    ? "bg-[#06141B] text-[#CCD0CF] dark:bg-[#CCD0CF] dark:text-[#06141B]"
                    : "text-[#253745] dark:text-[#9BA8AB] hover:text-[#06141B] dark:hover:text-[#CCD0CF]"
                )}
              >
                <Sun className="w-3.5 h-3.5" />
                <span>Light</span>
              </button>

              <button
                type="button"
                onClick={() => setTheme("system")}
                className={cn(
                  "inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-full text-xs font-medium transition-colors",
                  theme === "system"
                    ? "bg-[#06141B] text-[#CCD0CF] dark:bg-[#CCD0CF] dark:text-[#06141B]"
                    : "text-[#253745] dark:text-[#9BA8AB] hover:text-[#06141B] dark:hover:text-[#CCD0CF]"
                )}
              >
                <Laptop className="w-3.5 h-3.5" />
                <span>System</span>
              </button>
            </div>
          </div>

          {/* Search Defaults Row */}
          <div className="p-6 space-y-5">
            <div>
              <h3 className="text-base font-serif font-medium text-[#06141B] dark:text-[#CCD0CF]">
                Search Defaults
              </h3>
              <p className="text-xs text-[#253745] dark:text-[#9BA8AB] mt-0.5">
                Default retrieval strategy and result limit applied to new search sessions.
              </p>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
              <div className="space-y-2">
                <label
                  htmlFor="default-search-mode"
                  className="block text-xs font-medium text-[#06141B] dark:text-[#CCD0CF]"
                >
                  Default Retrieval Mode
                </label>
                <select
                  id="default-search-mode"
                  value={defaultMode}
                  onChange={(e) => onDefaultModeChange(e.target.value as SearchMode)}
                  className="w-full rounded-xl bg-[#E2E6E5] dark:bg-[#06141B] border border-[#9BA8AB] dark:border-[#253745] px-3.5 py-2.5 text-xs text-[#06141B] dark:text-[#CCD0CF] focus:outline-none focus:border-[#06141B] dark:focus:border-[#9BA8AB]"
                >
                  <option value="hybrid">Hybrid (Lexical + Semantic RRF — Recommended)</option>
                  <option value="keyword">Keyword Only (SQLite FTS5 BM25)</option>
                  <option value="semantic">Semantic Only (EmbeddingGemma 2 Vectors)</option>
                </select>
              </div>

              <div className="space-y-2">
                <label
                  htmlFor="default-results-limit"
                  className="block text-xs font-medium text-[#06141B] dark:text-[#CCD0CF]"
                >
                  Results Limit
                </label>
                <select
                  id="default-results-limit"
                  value={defaultLimit}
                  onChange={(e) => onDefaultLimitChange(Number(e.target.value))}
                  className="w-full rounded-xl bg-[#E2E6E5] dark:bg-[#06141B] border border-[#9BA8AB] dark:border-[#253745] px-3.5 py-2.5 text-xs text-[#06141B] dark:text-[#CCD0CF] focus:outline-none focus:border-[#06141B] dark:focus:border-[#9BA8AB]"
                >
                  <option value="10">10 results per query</option>
                  <option value="20">20 results per query (Default)</option>
                  <option value="50">50 results per query</option>
                </select>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ==================================================================== */}
      {/* SECTION 2: SYSTEM HEALTH & DIAGNOSTICS                                */}
      {/* ==================================================================== */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-[11px] font-mono uppercase tracking-widest text-[#4A5C6A] dark:text-[#9BA8AB]">
            System Health & Subsystems
          </h2>

          {systemStatus && (
            <button
              type="button"
              onClick={() => setIsDiagnosticsOpen(!isDiagnosticsOpen)}
              className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium text-[#253745] dark:text-[#9BA8AB] hover:text-[#06141B] dark:hover:text-[#CCD0CF] border border-[#9BA8AB] dark:border-[#253745] transition-colors"
            >
              <span>{isDiagnosticsOpen ? "Hide technical details" : "Show technical details"}</span>
              {isDiagnosticsOpen ? (
                <ChevronUp className="w-3.5 h-3.5" />
              ) : (
                <ChevronDown className="w-3.5 h-3.5" />
              )}
            </button>
          )}
        </div>

        {systemStatus ? (
          <div className="rounded-xl bg-[#D8DCDB] dark:bg-[#06141B]/55 border border-[#9BA8AB] dark:border-[#253745] overflow-hidden">
            {/* Summary Bar */}
            <div className="p-5 border-b border-[#9BA8AB] dark:border-[#253745] flex flex-wrap items-center justify-between gap-4">
              <div className="flex items-center gap-2.5">
                <span
                  className={cn(
                    "w-2 h-2 rounded-full",
                    systemStatus.status === "healthy"
                      ? "bg-[#2d6a4f] dark:bg-[#74c69d]"
                      : "bg-[#b5651d] dark:bg-[#fcd34d]"
                  )}
                />
                <span className="text-sm font-medium text-[#06141B] dark:text-[#CCD0CF]">
                  {systemStatus.status === "healthy"
                    ? "All local subsystems operational"
                    : "System operating in degraded mode"}
                </span>
              </div>
              <div className="text-xs font-mono text-[#4A5C6A] dark:text-[#9BA8AB]">
                {systemStatus.app_name} v{systemStatus.version} · {systemStatus.environment}
              </div>
            </div>

            {/* Detailed 3-Column Subsystem Table */}
            {isDiagnosticsOpen && (
              <div className="grid grid-cols-1 md:grid-cols-3 divide-y md:divide-y-0 md:divide-x divide-[#9BA8AB] dark:divide-[#253745]">
                {/* Column 1: SQLite & FTS5 */}
                <div className="p-5 space-y-3">
                  <div className="flex items-baseline justify-between">
                    <h3 className="text-sm font-serif font-medium text-[#06141B] dark:text-[#CCD0CF]">
                      SQLite & FTS5
                    </h3>
                    <span className="text-[11px] font-mono text-[#2d6a4f] dark:text-[#74c69d] capitalize">
                      {systemStatus.database.status}
                    </span>
                  </div>
                  <dl className="space-y-1.5 text-xs font-mono tabular-nums">
                    <div className="flex justify-between">
                      <dt className="font-sans text-[#4A5C6A] dark:text-[#9BA8AB]">WAL Mode</dt>
                      <dd className="text-[#06141B] dark:text-[#CCD0CF]">
                        {systemStatus.database.wal_mode ? "Enabled" : "Disabled"}
                      </dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="font-sans text-[#4A5C6A] dark:text-[#9BA8AB]">Tracked Files</dt>
                      <dd className="text-[#06141B] dark:text-[#CCD0CF]">
                        {formatNumber(systemStatus.database.total_files)}
                      </dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="font-sans text-[#4A5C6A] dark:text-[#9BA8AB]">Stored Chunks</dt>
                      <dd className="text-[#06141B] dark:text-[#CCD0CF]">
                        {formatNumber(systemStatus.database.total_chunks)}
                      </dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="font-sans text-[#4A5C6A] dark:text-[#9BA8AB]">Database Size</dt>
                      <dd className="text-[#06141B] dark:text-[#CCD0CF]">
                        {systemStatus.database.size_bytes
                          ? formatBytes(systemStatus.database.size_bytes)
                          : "N/A"}
                      </dd>
                    </div>
                  </dl>
                </div>

                {/* Column 2: ChromaDB Vector Store */}
                <div className="p-5 space-y-3">
                  <div className="flex items-baseline justify-between">
                    <h3 className="text-sm font-serif font-medium text-[#06141B] dark:text-[#CCD0CF]">
                      Vector Store
                    </h3>
                    <span className="text-[11px] font-mono text-[#2d6a4f] dark:text-[#74c69d] capitalize">
                      {systemStatus.vector_store.status}
                    </span>
                  </div>
                  <dl className="space-y-1.5 text-xs font-mono tabular-nums">
                    <div className="flex justify-between gap-2">
                      <dt className="font-sans text-[#4A5C6A] dark:text-[#9BA8AB]">Collection</dt>
                      <dd className="text-[#06141B] dark:text-[#CCD0CF] truncate max-w-[150px]">
                        {systemStatus.vector_store.collection_name}
                      </dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="font-sans text-[#4A5C6A] dark:text-[#9BA8AB]">Total Vectors</dt>
                      <dd className="text-[#06141B] dark:text-[#CCD0CF]">
                        {formatNumber(systemStatus.vector_store.total_vectors)}
                      </dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="font-sans text-[#4A5C6A] dark:text-[#9BA8AB]">Unembedded</dt>
                      <dd className="text-[#06141B] dark:text-[#CCD0CF]">
                        {formatNumber(systemStatus.vector_store.unembedded_chunks)}
                      </dd>
                    </div>
                  </dl>
                </div>

                {/* Column 3: Embedding Model */}
                <div className="p-5 space-y-3">
                  <div className="flex items-baseline justify-between">
                    <h3 className="text-sm font-serif font-medium text-[#06141B] dark:text-[#CCD0CF]">
                      Embedding Model
                    </h3>
                    <span className="text-[11px] font-mono text-[#2d6a4f] dark:text-[#74c69d] capitalize">
                      {systemStatus.embedding_model.status}
                    </span>
                  </div>
                  <dl className="space-y-1.5 text-xs font-mono tabular-nums">
                    <div className="flex justify-between">
                      <dt className="font-sans text-[#4A5C6A] dark:text-[#9BA8AB]">Dimensions</dt>
                      <dd className="text-[#06141B] dark:text-[#CCD0CF]">
                        {systemStatus.embedding_model.dimension}D
                      </dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="font-sans text-[#4A5C6A] dark:text-[#9BA8AB]">Device</dt>
                      <dd className="text-[#06141B] dark:text-[#CCD0CF] uppercase">
                        {systemStatus.embedding_model.device}
                      </dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="font-sans text-[#4A5C6A] dark:text-[#9BA8AB]">Local Weights</dt>
                      <dd className="text-[#06141B] dark:text-[#CCD0CF]">
                        {systemStatus.embedding_model.local_weights_present
                          ? "Verified"
                          : "Missing"}
                      </dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="font-sans text-[#4A5C6A] dark:text-[#9BA8AB]">Memory State</dt>
                      <dd className="text-[#06141B] dark:text-[#CCD0CF]">
                        {systemStatus.embedding_model.is_loaded ? "Resident" : "On-Demand"}
                      </dd>
                    </div>
                  </dl>
                </div>
              </div>
            )}
          </div>
        ) : error ? (
          <div className="p-5 rounded-xl bg-[#D8DCDB] dark:bg-[#06141B]/65 border border-[#9b2226]/30 text-xs text-[#9b2226] dark:text-[#f2b8b5] flex items-center justify-between gap-4">
            <span className="font-mono">{error}</span>
            <Button variant="secondary" size="xs" onClick={fetchStatus}>
              Retry
            </Button>
          </div>
        ) : (
          <div className="p-8 text-center rounded-xl bg-[#D8DCDB] dark:bg-[#06141B]/55 border border-[#9BA8AB] dark:border-[#253745] text-xs text-[#4A5C6A] dark:text-[#9BA8AB]">
            Loading subsystem diagnostics...
          </div>
        )}
      </div>
    </div>
  );
}
