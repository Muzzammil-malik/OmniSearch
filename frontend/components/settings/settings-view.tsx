"use client";

import React, { useEffect, useState } from "react";
import {
  Sun,
  Moon,
  Laptop,
  Database,
  Cpu,
  Layers,
  RotateCw,
  ChevronDown,
  ChevronUp,
  Activity,
} from "lucide-react";
import { systemApi } from "@/lib/api";
import { SearchMode, SystemStatusResponse } from "@/lib/types";
import { formatBytes, formatNumber } from "@/lib/utils";
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
  const [isDiagnosticsOpen, setIsDiagnosticsOpen] = useState(false);

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
    <div className="p-6 sm:p-10 max-w-5xl mx-auto space-y-10 font-sans">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-6 border-b border-slate-200 dark:border-navy-800">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white">
            Settings & System
          </h1>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
            Customize search preferences, theme appearance, and check system health.
          </p>
        </div>

        <Button variant="outline" size="sm" onClick={fetchStatus} disabled={isLoading}>
          <RotateCw className={`w-4 h-4 mr-1.5 ${isLoading ? "animate-spin" : ""}`} />
          Refresh Status
        </Button>
      </div>

      {/* ==================================================================== */}
      {/* SECTION 1: SETTINGS                                                  */}
      {/* ==================================================================== */}
      <div className="space-y-6">
        <div>
          <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500">
            Preferences
          </h2>
        </div>

        {/* Appearance Card */}
        <div className="p-6 rounded-2xl bg-white dark:bg-navy-900 border border-slate-200 dark:border-navy-800 shadow-sm space-y-4">
          <div>
            <h3 className="text-base font-semibold text-slate-900 dark:text-slate-100">
              Appearance
            </h3>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
              Select your interface color theme.
            </p>
          </div>

          <div className="grid grid-cols-3 gap-3 max-w-md">
            <button
              onClick={() => setTheme("dark")}
              className={`p-3.5 rounded-xl border flex flex-col items-center gap-2 text-xs font-medium transition-all ${
                theme === "dark"
                  ? "bg-cyan-500/10 border-cyan-500/40 text-cyan-600 dark:text-cyan-400"
                  : "bg-slate-50 dark:bg-navy-850 border-slate-200 dark:border-navy-750 text-slate-600 dark:text-slate-400 hover:border-slate-300"
              }`}
            >
              <Moon className="w-5 h-5" />
              <span>Dark</span>
            </button>

            <button
              onClick={() => setTheme("light")}
              className={`p-3.5 rounded-xl border flex flex-col items-center gap-2 text-xs font-medium transition-all ${
                theme === "light"
                  ? "bg-cyan-500/10 border-cyan-500/40 text-cyan-600 dark:text-cyan-400"
                  : "bg-slate-50 dark:bg-navy-850 border-slate-200 dark:border-navy-750 text-slate-600 dark:text-slate-400 hover:border-slate-300"
              }`}
            >
              <Sun className="w-5 h-5" />
              <span>Light</span>
            </button>

            <button
              onClick={() => setTheme("system")}
              className={`p-3.5 rounded-xl border flex flex-col items-center gap-2 text-xs font-medium transition-all ${
                theme === "system"
                  ? "bg-cyan-500/10 border-cyan-500/40 text-cyan-600 dark:text-cyan-400"
                  : "bg-slate-50 dark:bg-navy-850 border-slate-200 dark:border-navy-750 text-slate-600 dark:text-slate-400 hover:border-slate-300"
              }`}
            >
              <Laptop className="w-5 h-5" />
              <span>System</span>
            </button>
          </div>
        </div>

        {/* Search Defaults Card */}
        <div className="p-6 rounded-2xl bg-white dark:bg-navy-900 border border-slate-200 dark:border-navy-800 shadow-sm space-y-6">
          <div>
            <h3 className="text-base font-semibold text-slate-900 dark:text-slate-100">
              Search Defaults
            </h3>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
              Default strategy and result quantity applied on new searches.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
            {/* Default Search Mode */}
            <div className="space-y-2">
              <label className="text-xs font-medium text-slate-700 dark:text-slate-300">
                Default Search Mode
              </label>
              <select
                value={defaultMode}
                onChange={(e) => onDefaultModeChange(e.target.value as SearchMode)}
                className="w-full rounded-xl bg-slate-50 dark:bg-navy-850 border border-slate-200 dark:border-navy-750 p-2.5 text-xs text-slate-900 dark:text-slate-100 focus:outline-none focus:border-cyan-500"
              >
                <option value="hybrid">Hybrid (Lexical + Semantic RRF - Recommended)</option>
                <option value="keyword">Keyword Only (SQLite FTS5 BM25)</option>
                <option value="semantic">Semantic Only (EmbeddingGemma 2 Vectors)</option>
              </select>
            </div>

            {/* Results per page */}
            <div className="space-y-2">
              <label className="text-xs font-medium text-slate-700 dark:text-slate-300">
                Results Limit
              </label>
              <select
                value={defaultLimit}
                onChange={(e) => onDefaultLimitChange(Number(e.target.value))}
                className="w-full rounded-xl bg-slate-50 dark:bg-navy-850 border border-slate-200 dark:border-navy-750 p-2.5 text-xs text-slate-900 dark:text-slate-100 focus:outline-none focus:border-cyan-500"
              >
                <option value="10">10 results per query</option>
                <option value="20">20 results per query (Default)</option>
                <option value="50">50 results per query</option>
              </select>
            </div>
          </div>
        </div>
      </div>

      {/* ==================================================================== */}
      {/* SECTION 2: SYSTEM HEALTH & ADVANCED DIAGNOSTICS                       */}
      {/* ==================================================================== */}
      <div className="space-y-4 pt-2 border-t border-slate-200 dark:border-navy-800">
        <div>
          <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500">
            System Health & Diagnostics
          </h2>
        </div>

        {systemStatus ? (
          <div className="space-y-4">
            {/* Health Overview Summary Card */}
            <div className="p-5 rounded-2xl bg-white dark:bg-navy-900 border border-slate-200 dark:border-navy-800 shadow-sm space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2.5">
                  <span
                    className={`w-2.5 h-2.5 rounded-full ${
                      systemStatus.status === "healthy"
                        ? "bg-emerald-500 shadow-sm shadow-emerald-500/50"
                        : "bg-amber-500 animate-pulse"
                    }`}
                  />
                  <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                    {systemStatus.status === "healthy"
                      ? "All Subsystems Operational"
                      : "System Degraded"}
                  </h3>
                </div>
                <span className="font-mono text-xs text-slate-400">
                  {systemStatus.app_name} v{systemStatus.version}
                </span>
              </div>

              {/* Subsystem Health Snapshot */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
                <div className="p-3 rounded-xl bg-slate-50 dark:bg-navy-850 border border-slate-200 dark:border-navy-750 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Database className="w-3.5 h-3.5 text-cyan-500" />
                    <span className="font-medium text-slate-700 dark:text-slate-300">Database</span>
                  </div>
                  <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 font-semibold">
                    {systemStatus.database.status}
                  </span>
                </div>

                <div className="p-3 rounded-xl bg-slate-50 dark:bg-navy-850 border border-slate-200 dark:border-navy-750 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Layers className="w-3.5 h-3.5 text-cyan-500" />
                    <span className="font-medium text-slate-700 dark:text-slate-300">Vector Store</span>
                  </div>
                  <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 font-semibold">
                    {systemStatus.vector_store.status}
                  </span>
                </div>

                <div className="p-3 rounded-xl bg-slate-50 dark:bg-navy-850 border border-slate-200 dark:border-navy-750 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Cpu className="w-3.5 h-3.5 text-cyan-500" />
                    <span className="font-medium text-slate-700 dark:text-slate-300">Embedding Model</span>
                  </div>
                  <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 font-semibold">
                    {systemStatus.embedding_model.status}
                  </span>
                </div>
              </div>

              {/* Expandable Technical Diagnostics Toggle */}
              <div className="pt-2 border-t border-slate-100 dark:border-navy-800">
                <button
                  type="button"
                  onClick={() => setIsDiagnosticsOpen(!isDiagnosticsOpen)}
                  className="flex items-center gap-1.5 text-xs font-medium text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200 transition-colors"
                >
                  <Activity className="w-3.5 h-3.5" />
                  <span>Technical Diagnostics</span>
                  {isDiagnosticsOpen ? (
                    <ChevronUp className="w-3.5 h-3.5 text-slate-400 ml-0.5" />
                  ) : (
                    <ChevronDown className="w-3.5 h-3.5 text-slate-400 ml-0.5" />
                  )}
                </button>
              </div>
            </div>

            {/* Detailed Technical Subsystem Cards (Secondary / Expandable) */}
            {isDiagnosticsOpen && (
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 animate-in fade-in duration-100">
                {/* SQLite Status Card */}
                <div className="p-5 rounded-2xl bg-white dark:bg-navy-900 border border-slate-200 dark:border-navy-800 space-y-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 text-xs font-semibold text-slate-900 dark:text-slate-100">
                      <Database className="w-4 h-4 text-cyan-500" />
                      <span>SQLite & FTS5</span>
                    </div>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">
                      {systemStatus.database.status}
                    </span>
                  </div>

                  <div className="space-y-1.5 text-xs text-slate-500 dark:text-slate-400 font-mono">
                    <div className="flex justify-between">
                      <span className="font-sans">WAL Mode:</span>
                      <span className="text-slate-700 dark:text-slate-200">
                        {systemStatus.database.wal_mode ? "Active" : "Inactive"}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="font-sans">Tracked Files:</span>
                      <span className="text-slate-700 dark:text-slate-200">
                        {formatNumber(systemStatus.database.total_files)}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="font-sans">Stored Chunks:</span>
                      <span className="text-slate-700 dark:text-slate-200">
                        {formatNumber(systemStatus.database.total_chunks)}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="font-sans">DB Size:</span>
                      <span className="text-slate-700 dark:text-slate-200">
                        {systemStatus.database.size_bytes
                          ? formatBytes(systemStatus.database.size_bytes)
                          : "N/A"}
                      </span>
                    </div>
                  </div>
                </div>

                {/* ChromaDB Status Card */}
                <div className="p-5 rounded-2xl bg-white dark:bg-navy-900 border border-slate-200 dark:border-navy-800 space-y-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 text-xs font-semibold text-slate-900 dark:text-slate-100">
                      <Layers className="w-4 h-4 text-cyan-500" />
                      <span>ChromaDB Vectors</span>
                    </div>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">
                      {systemStatus.vector_store.status}
                    </span>
                  </div>

                  <div className="space-y-1.5 text-xs text-slate-500 dark:text-slate-400 font-mono">
                    <div className="flex justify-between">
                      <span className="font-sans">Collection:</span>
                      <span className="text-slate-700 dark:text-slate-200 truncate max-w-[140px]">
                        {systemStatus.vector_store.collection_name}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="font-sans">Total Vectors:</span>
                      <span className="text-cyan-600 dark:text-cyan-400 font-semibold">
                        {formatNumber(systemStatus.vector_store.total_vectors)}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="font-sans">Pending Chunks:</span>
                      <span className="text-slate-700 dark:text-slate-200">
                        {formatNumber(systemStatus.vector_store.unembedded_chunks)}
                      </span>
                    </div>
                  </div>
                </div>

                {/* EmbeddingGemma 2 Status Card */}
                <div className="p-5 rounded-2xl bg-white dark:bg-navy-900 border border-slate-200 dark:border-navy-800 space-y-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 text-xs font-semibold text-slate-900 dark:text-slate-100">
                      <Cpu className="w-4 h-4 text-cyan-500" />
                      <span>EmbeddingGemma 2</span>
                    </div>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">
                      {systemStatus.embedding_model.status}
                    </span>
                  </div>

                  <div className="space-y-1.5 text-xs text-slate-500 dark:text-slate-400 font-mono">
                    <div className="flex justify-between">
                      <span className="font-sans">Dimensions:</span>
                      <span className="text-slate-700 dark:text-slate-200">
                        {systemStatus.embedding_model.dimension}D
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="font-sans">Target Device:</span>
                      <span className="text-slate-700 dark:text-slate-200 uppercase">
                        {systemStatus.embedding_model.device}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="font-sans">Weights Verified:</span>
                      <span className="text-emerald-500">
                        {systemStatus.embedding_model.local_weights_present ? "Yes" : "No"}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="font-sans">Loaded in RAM:</span>
                      <span className="text-slate-700 dark:text-slate-200">
                        {systemStatus.embedding_model.is_loaded ? "Resident" : "On-Demand"}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        ) : error ? (
          <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/20 text-xs text-red-500">
            {error}
          </div>
        ) : (
          <div className="p-8 text-center text-xs text-slate-500">
            Loading system diagnostics...
          </div>
        )}
      </div>
    </div>
  );
}
