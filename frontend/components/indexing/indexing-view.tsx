"use client";

import React, { useEffect, useState, useCallback } from "react";
import {
  Cpu,
  Play,
  RotateCw,
  Layers,
  HardDrive,
  FileText,
  Sparkles,
  ChevronDown,
  ChevronUp,
  SlidersHorizontal,
} from "lucide-react";
import { indexingApi } from "@/lib/api";
import {
  IndexJobResponse,
  IndexingStatsResponse,
  IndexingStatusResponse,
} from "@/lib/types";
import { formatBytes, formatNumber, formatRelativeTime } from "@/lib/utils";
import { Button } from "../ui/button";

interface IndexingViewProps {
  onIndexingStateChange?: (isActive: boolean) => void;
}

export function IndexingView({ onIndexingStateChange }: IndexingViewProps) {
  const [status, setStatus] = useState<IndexingStatusResponse | null>(null);
  const [stats, setStats] = useState<IndexingStatsResponse | null>(null);
  const [jobs, setJobs] = useState<IndexJobResponse[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isStarting, setIsStarting] = useState(false);
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  // Advanced options toggle
  const [isAdvancedOpen, setIsAdvancedOpen] = useState(false);

  // Indexing options
  const [forceReindex, setForceReindex] = useState(false);
  const [reconcileDeleted, setReconcileDeleted] = useState(true);
  const [generateEmbeddings, setGenerateEmbeddings] = useState(true);

  const fetchIndexingData = useCallback(async () => {
    try {
      const [statusRes, statsRes, jobsRes] = await Promise.all([
        indexingApi.getStatus(),
        indexingApi.getStats(),
        indexingApi.getJobs(15),
      ]);
      setStatus(statusRes);
      setStats(statsRes);
      setJobs(jobsRes);
      if (onIndexingStateChange) {
        onIndexingStateChange(statusRes.is_indexing);
      }
    } catch {
      // Ignore background refresh errors
    } finally {
      setIsLoading(false);
    }
  }, [onIndexingStateChange]);

  useEffect(() => {
    fetchIndexingData();
    const intervalTime = status?.is_indexing ? 3000 : 10000;
    const interval = setInterval(fetchIndexingData, intervalTime);
    return () => clearInterval(interval);
  }, [status?.is_indexing, fetchIndexingData]);

  const handleStartIndexing = async () => {
    setIsStarting(true);
    setActionMessage(null);
    try {
      await indexingApi.start({
        force_reindex: forceReindex,
        reconcile_deleted: reconcileDeleted,
        generate_embeddings: generateEmbeddings,
        background: true,
      });
      setActionMessage("Indexing started in background.");
      fetchIndexingData();
    } catch (err: unknown) {
      setActionMessage(
        `Indexing failed: ${err instanceof Error ? err.message : "Error"}`
      );
    } finally {
      setIsStarting(false);
    }
  };

  const currentJob = status?.current_job;

  return (
    <div className="p-6 sm:p-10 max-w-5xl mx-auto space-y-8 font-sans">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-6 border-b border-slate-200 dark:border-navy-800">
        <div>
          <div className="flex items-center gap-3 flex-wrap">
            <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white">
              Index your library
            </h1>
            {status?.watcher?.active ? (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
                {status.watcher.current_file
                  ? `Processing: ${status.watcher.current_file}`
                  : status.watcher.pending_events > 0 || status.watcher.coordinator_queue_size > 0
                  ? "Synchronizing changes"
                  : "Watching automatically"}
              </span>
            ) : (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-500/10 text-slate-600 dark:text-slate-400 border border-slate-500/20">
                <span className="h-1.5 w-1.5 rounded-full bg-slate-400" />
                Library up to date
              </span>
            )}
          </div>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
            Keep your documents searchable and up to date.
          </p>
        </div>

        <Button
          variant="outline"
          size="sm"
          onClick={fetchIndexingData}
          disabled={isLoading}
        >
          <RotateCw className={`w-4 h-4 mr-1.5 ${isLoading ? "animate-spin" : ""}`} />
          Refresh Status
        </Button>
      </div>

      {/* Action Notification */}
      {actionMessage && (
        <div className="p-3.5 rounded-xl bg-cyan-500/10 border border-cyan-500/20 text-xs text-cyan-600 dark:text-cyan-400 flex items-center justify-between">
          <span>{actionMessage}</span>
          <button onClick={() => setActionMessage(null)} className="font-semibold underline ml-2">
            Dismiss
          </button>
        </div>
      )}

      {/* Active Job Progress Banner */}
      {status?.is_indexing && currentJob && (
        <div className="p-5 rounded-2xl bg-cyan-500/5 border border-cyan-500/30 space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="flex h-2.5 w-2.5 relative">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-cyan-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-cyan-500" />
              </span>
              <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                Indexing in progress (Job #{currentJob.id})
              </h3>
            </div>
            <span className="text-xs font-mono text-cyan-600 dark:text-cyan-400">
              {currentJob.processed_files} / {currentJob.total_files} files
            </span>
          </div>

          {/* Progress bar */}
          <div className="w-full h-2 bg-slate-200 dark:bg-navy-800 rounded-full overflow-hidden">
            <div
              className="h-full bg-cyan-500 transition-all duration-300"
              style={{
                width: `${
                  currentJob.total_files > 0
                    ? Math.min(100, (currentJob.processed_files / currentJob.total_files) * 100)
                    : 0
                }%`,
              }}
            />
          </div>

          <div className="flex items-center gap-4 text-xs text-slate-500 dark:text-slate-400">
            <span>Successful: {currentJob.successful_files}</span>
            <span>·</span>
            <span>Skipped: {currentJob.skipped_files}</span>
            <span>·</span>
            <span className={currentJob.failed_files > 0 ? "text-red-500" : ""}>
              Failed: {currentJob.failed_files}
            </span>
          </div>
        </div>
      )}

      {/* Main Indexing Action Card */}
      <div className="p-6 rounded-2xl bg-white dark:bg-navy-900 border border-slate-200 dark:border-navy-800 shadow-sm space-y-5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h3 className="text-base font-semibold text-slate-900 dark:text-slate-100 flex items-center gap-2">
              <Cpu className="w-4 h-4 text-cyan-500" />
              Run Library Indexing
            </h3>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1 max-w-lg leading-relaxed">
              Scans all active library folders for new and modified documents, extracting text and updating keyword and vector indices.
            </p>
          </div>

          <Button
            variant="primary"
            size="md"
            onClick={handleStartIndexing}
            isLoading={isStarting || status?.is_indexing}
            disabled={status?.is_indexing}
            className="shrink-0"
          >
            <Play className="w-4 h-4 mr-2" />
            {status?.is_indexing ? "Indexing..." : "Index All Active Folders"}
          </Button>
        </div>

        {/* Expandable Advanced Indexing Options */}
        <div className="pt-2 border-t border-slate-100 dark:border-navy-800/80">
          <button
            type="button"
            onClick={() => setIsAdvancedOpen(!isAdvancedOpen)}
            className="flex items-center gap-1.5 text-xs font-medium text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200 transition-colors"
          >
            <SlidersHorizontal className="w-3.5 h-3.5" />
            <span>Advanced indexing options</span>
            {isAdvancedOpen ? (
              <ChevronUp className="w-3.5 h-3.5 text-slate-400 ml-0.5" />
            ) : (
              <ChevronDown className="w-3.5 h-3.5 text-slate-400 ml-0.5" />
            )}
          </button>

          {isAdvancedOpen && (
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-3.5 animate-in fade-in duration-100">
              <label className="flex items-center gap-2 text-xs text-slate-700 dark:text-slate-300 cursor-pointer">
                <input
                  type="checkbox"
                  checked={generateEmbeddings}
                  onChange={(e) => setGenerateEmbeddings(e.target.checked)}
                  className="rounded border-slate-300 text-cyan-600 focus:ring-cyan-500"
                />
                <span>Generate Embeddings</span>
              </label>

              <label className="flex items-center gap-2 text-xs text-slate-700 dark:text-slate-300 cursor-pointer">
                <input
                  type="checkbox"
                  checked={reconcileDeleted}
                  onChange={(e) => setReconcileDeleted(e.target.checked)}
                  className="rounded border-slate-300 text-cyan-600 focus:ring-cyan-500"
                />
                <span>Prune Deleted Files</span>
              </label>

              <label className="flex items-center gap-2 text-xs text-slate-700 dark:text-slate-300 cursor-pointer">
                <input
                  type="checkbox"
                  checked={forceReindex}
                  onChange={(e) => setForceReindex(e.target.checked)}
                  className="rounded border-slate-300 text-cyan-600 focus:ring-cyan-500"
                />
                <span>Force Full Re-extraction</span>
              </label>
            </div>
          )}
        </div>
      </div>

      {/* Global Statistics Grid */}
      {stats && (
        <div>
          <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500 mb-3">
            Library Metrics
          </h3>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="p-4 rounded-xl bg-white dark:bg-navy-900 border border-slate-200 dark:border-navy-800">
              <div className="flex items-center gap-2 text-slate-400 text-xs mb-1">
                <FileText className="w-3.5 h-3.5" />
                <span>Tracked Files</span>
              </div>
              <div className="text-xl font-bold font-mono text-slate-900 dark:text-slate-100">
                {formatNumber(stats.total_files)}
              </div>
              <span className="text-[11px] text-emerald-500 font-sans">
                {formatNumber(stats.successful_files)} indexed
              </span>
            </div>

            <div className="p-4 rounded-xl bg-white dark:bg-navy-900 border border-slate-200 dark:border-navy-800">
              <div className="flex items-center gap-2 text-slate-400 text-xs mb-1">
                <Layers className="w-3.5 h-3.5" />
                <span>Total Chunks</span>
              </div>
              <div className="text-xl font-bold font-mono text-slate-900 dark:text-slate-100">
                {formatNumber(stats.total_chunks)}
              </div>
              <span className="text-[11px] text-slate-500 dark:text-slate-400 font-sans">
                in search index
              </span>
            </div>

            {/* User-friendly Vector Embeddings metric card */}
            <div className="p-4 rounded-xl bg-white dark:bg-navy-900 border border-slate-200 dark:border-navy-800">
              <div className="flex items-center gap-2 text-slate-400 text-xs mb-1">
                <Sparkles className="w-3.5 h-3.5 text-cyan-500" />
                <span>Vector Embeddings</span>
              </div>
              <div className="text-xl font-bold font-mono text-cyan-600 dark:text-cyan-400">
                {formatNumber(stats.embedded_chunks)} ready
              </div>
              <span className="text-[11px] text-slate-500 dark:text-slate-400 font-sans">
                {stats.unembedded_chunks > 0
                  ? `${formatNumber(stats.unembedded_chunks)} pending`
                  : "All ready · 0 pending"}
              </span>
            </div>

            <div className="p-4 rounded-xl bg-white dark:bg-navy-900 border border-slate-200 dark:border-navy-800">
              <div className="flex items-center gap-2 text-slate-400 text-xs mb-1">
                <HardDrive className="w-3.5 h-3.5" />
                <span>Storage Footprint</span>
              </div>
              <div className="text-xl font-bold font-mono text-slate-900 dark:text-slate-100">
                {formatBytes(stats.total_size_bytes)}
              </div>
              <span className="text-[11px] text-slate-500 dark:text-slate-400 font-sans">
                across {stats.total_folders} folder{stats.total_folders === 1 ? "" : "s"}
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Recent Jobs History Table */}
      <div>
        <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500 mb-3">
          Recent Indexing History
        </h3>

        {jobs.length > 0 ? (
          <div className="rounded-2xl border border-slate-200 dark:border-navy-800 bg-white dark:bg-navy-900 overflow-hidden shadow-sm">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-50 dark:bg-navy-850 border-b border-slate-200 dark:border-navy-800 text-slate-500 dark:text-slate-400 font-medium">
                  <tr>
                    <th className="py-3 px-4">Job ID</th>
                    <th className="py-3 px-4">Status</th>
                    <th className="py-3 px-4">Files</th>
                    <th className="py-3 px-4">Success</th>
                    <th className="py-3 px-4">Skipped</th>
                    <th className="py-3 px-4">Failed</th>
                    <th className="py-3 px-4">Started</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200 dark:divide-navy-800 font-mono">
                  {jobs.map((job) => (
                    <tr key={job.id} className="hover:bg-slate-50/50 dark:hover:bg-navy-850/50">
                      <td className="py-3 px-4 font-semibold text-slate-900 dark:text-slate-200">
                        #{job.id}
                      </td>
                      <td className="py-3 px-4 font-sans">
                        <span
                          className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium capitalize ${
                            job.status === "completed"
                              ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20"
                              : job.status === "completed_with_errors"
                              ? "bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20"
                              : job.status === "running"
                              ? "bg-cyan-500/10 text-cyan-600 dark:text-cyan-400 border border-cyan-500/20"
                              : "bg-red-500/10 text-red-600 dark:text-red-400 border border-red-500/20"
                          }`}
                        >
                          {job.status.replace(/_/g, " ")}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-slate-700 dark:text-slate-300">
                        {job.processed_files} / {job.total_files}
                      </td>
                      <td className="py-3 px-4 text-emerald-600 dark:text-emerald-400">
                        {job.successful_files}
                      </td>
                      <td className="py-3 px-4 text-slate-500 dark:text-slate-400">
                        {job.skipped_files}
                      </td>
                      <td className="py-3 px-4 text-red-500">
                        {job.failed_files}
                      </td>
                      <td className="py-3 px-4 text-slate-500 dark:text-slate-400 font-sans">
                        {formatRelativeTime(job.started_at)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ) : (
          <div className="p-8 text-center rounded-2xl bg-white dark:bg-navy-900 border border-slate-200 dark:border-navy-800 text-xs text-slate-500">
            No indexing jobs recorded yet.
          </div>
        )}
      </div>
    </div>
  );
}
