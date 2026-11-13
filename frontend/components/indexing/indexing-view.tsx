"use client";

import React, { useEffect, useState, useCallback } from "react";
import {
  Play,
  RotateCw,
  ChevronDown,
  ChevronUp,
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

  const watcherText = status?.watcher?.active
    ? status.watcher.current_file
      ? `Processing: ${status.watcher.current_file}`
      : status.watcher.pending_events > 0 || status.watcher.coordinator_queue_size > 0
      ? "Synchronizing filesystem changes"
      : "Filesystem watcher active"
    : "Index synchronized";

  return (
    <div className="px-6 sm:px-10 py-8 sm:py-10 max-w-5xl mx-auto space-y-10 font-sans">
      {/* Top Editorial Header */}
      <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4 pb-6 border-b border-[#9BA8AB] dark:border-[#253745]">
        <div>
          <div className="flex items-center gap-2 text-[11px] font-mono uppercase tracking-widest text-[#4A5C6A] dark:text-[#9BA8AB] mb-1.5">
            <span>Indexing Engine</span>
            <span aria-hidden="true">·</span>
            <span className="text-[#253745] dark:text-[#CCD0CF] normal-case tracking-normal">
              {watcherText}
            </span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-serif font-normal tracking-tight text-[#06141B] dark:text-[#CCD0CF]">
            Index & Extraction Pipeline
          </h1>
          <p className="text-xs sm:text-sm text-[#253745] dark:text-[#9BA8AB] mt-1">
            Extract document text, synchronize lexical FTS5 tables, and compute local vector embeddings.
          </p>
        </div>

        <Button
          variant="outline"
          size="sm"
          onClick={fetchIndexingData}
          disabled={isLoading}
        >
          <RotateCw className={`w-3.5 h-3.5 mr-1.5 ${isLoading ? "animate-spin" : ""}`} />
          Refresh status
        </Button>
      </div>

      {/* Action Notification */}
      {actionMessage && (
        <div className="px-4 py-3 rounded-xl bg-[#D8DCDB] dark:bg-[#06141B]/65 border border-[#9BA8AB] dark:border-[#253745] text-xs text-[#06141B] dark:text-[#CCD0CF] flex items-center justify-between gap-4">
          <span>{actionMessage}</span>
          <button
            type="button"
            onClick={() => setActionMessage(null)}
            className="px-2.5 py-0.5 rounded-full text-[11px] font-medium text-[#253745] dark:text-[#9BA8AB] hover:text-[#06141B] dark:hover:text-[#CCD0CF]"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Active Job Progress Panel */}
      {status?.is_indexing && currentJob && (
        <div className="p-6 rounded-xl bg-[#11212D] text-[#CCD0CF] dark:bg-[#253745] border border-[#4A5C6A] space-y-4">
          <div className="flex items-baseline justify-between gap-4">
            <div>
              <p className="text-[10px] font-mono uppercase tracking-widest text-[#9BA8AB] mb-1">
                Active Operation
              </p>
              <h3 className="text-base font-serif font-normal text-[#CCD0CF]">
                Indexing Job #{currentJob.id} in progress
              </h3>
            </div>
            <span className="text-xs font-mono tabular-nums text-[#9BA8AB]">
              {currentJob.processed_files} / {currentJob.total_files} files
            </span>
          </div>

          {/* Restrained Technical Progress Bar */}
          <div className="w-full h-1.5 bg-[#06141B] rounded-full overflow-hidden">
            <div
              className="h-full bg-[#CCD0CF] transition-all duration-300 ease-out"
              style={{
                width: `${
                  currentJob.total_files > 0
                    ? Math.min(100, (currentJob.processed_files / currentJob.total_files) * 100)
                    : 0
                }%`,
              }}
            />
          </div>

          <div className="flex items-center gap-3 text-xs font-mono tabular-nums text-[#9BA8AB]">
            <span>Successful: {currentJob.successful_files}</span>
            <span aria-hidden="true">·</span>
            <span>Skipped: {currentJob.skipped_files}</span>
            <span aria-hidden="true">·</span>
            <span className={currentJob.failed_files > 0 ? "text-[#f2b8b5]" : ""}>
              Failed: {currentJob.failed_files}
            </span>
          </div>
        </div>
      )}

      {/* Primary Indexing Control Surface */}
      <div className="p-6 rounded-xl bg-[#D8DCDB] dark:bg-[#06141B]/55 border border-[#9BA8AB] dark:border-[#253745] space-y-5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h2 className="text-lg font-serif font-medium text-[#06141B] dark:text-[#CCD0CF]">
              Run Library Indexing
            </h2>
            <p className="text-xs text-[#253745] dark:text-[#9BA8AB] mt-1 max-w-xl leading-relaxed">
              Scans all enabled library directories for new or modified files, extracts structured passages, and updates both keyword and vector indices.
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
            <Play className="w-3.5 h-3.5 mr-1.5" />
            {status?.is_indexing ? "Indexing..." : "Index all active folders"}
          </Button>
        </div>

        {/* Expandable Advanced Options */}
        <div className="pt-3 border-t border-[#9BA8AB]/60 dark:border-[#253745]">
          <button
            type="button"
            onClick={() => setIsAdvancedOpen(!isAdvancedOpen)}
            className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium text-[#253745] dark:text-[#9BA8AB] hover:text-[#06141B] dark:hover:text-[#CCD0CF] hover:bg-[#06141B]/[0.06] dark:hover:bg-[#253745] transition-colors"
          >
            <span>Indexing parameters</span>
            {isAdvancedOpen ? (
              <ChevronUp className="w-3.5 h-3.5" />
            ) : (
              <ChevronDown className="w-3.5 h-3.5" />
            )}
          </button>

          {isAdvancedOpen && (
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-4 px-1">
              <label className="flex items-center gap-2.5 text-xs text-[#06141B] dark:text-[#CCD0CF] cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={generateEmbeddings}
                  onChange={(e) => setGenerateEmbeddings(e.target.checked)}
                  className="rounded border-[#9BA8AB] dark:border-[#4A5C6A] text-[#06141B] focus:ring-[#4A5C6A]"
                />
                <span>Generate vector embeddings</span>
              </label>

              <label className="flex items-center gap-2.5 text-xs text-[#06141B] dark:text-[#CCD0CF] cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={reconcileDeleted}
                  onChange={(e) => setReconcileDeleted(e.target.checked)}
                  className="rounded border-[#9BA8AB] dark:border-[#4A5C6A] text-[#06141B] focus:ring-[#4A5C6A]"
                />
                <span>Prune deleted files</span>
              </label>

              <label className="flex items-center gap-2.5 text-xs text-[#06141B] dark:text-[#CCD0CF] cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={forceReindex}
                  onChange={(e) => setForceReindex(e.target.checked)}
                  className="rounded border-[#9BA8AB] dark:border-[#4A5C6A] text-[#06141B] focus:ring-[#4A5C6A]"
                />
                <span>Force full re-extraction</span>
              </label>
            </div>
          )}
        </div>
      </div>

      {/* Editorial Stat Strip */}
      {stats && (
        <div>
          <h2 className="text-[11px] font-mono uppercase tracking-widest text-[#4A5C6A] dark:text-[#9BA8AB] mb-3">
            Corpus Metrics
          </h2>
          <div className="grid grid-cols-2 sm:grid-cols-4 divide-y sm:divide-y-0 sm:divide-x divide-[#9BA8AB] dark:divide-[#253745] rounded-xl bg-[#D8DCDB] dark:bg-[#06141B]/55 border border-[#9BA8AB] dark:border-[#253745]">
            <div className="p-5">
              <div className="text-xs text-[#4A5C6A] dark:text-[#9BA8AB] mb-1">
                Tracked Files
              </div>
              <div className="text-2xl font-serif font-normal font-mono tabular-nums text-[#06141B] dark:text-[#CCD0CF]">
                {formatNumber(stats.total_files)}
              </div>
              <div className="text-[11px] text-[#253745] dark:text-[#9BA8AB] mt-1 font-mono tabular-nums">
                {formatNumber(stats.successful_files)} indexed
              </div>
            </div>

            <div className="p-5">
              <div className="text-xs text-[#4A5C6A] dark:text-[#9BA8AB] mb-1">
                Indexed Chunks
              </div>
              <div className="text-2xl font-serif font-normal font-mono tabular-nums text-[#06141B] dark:text-[#CCD0CF]">
                {formatNumber(stats.total_chunks)}
              </div>
              <div className="text-[11px] text-[#253745] dark:text-[#9BA8AB] mt-1">
                Searchable passages
              </div>
            </div>

            <div className="p-5">
              <div className="text-xs text-[#4A5C6A] dark:text-[#9BA8AB] mb-1">
                Vector Embeddings
              </div>
              <div className="text-2xl font-serif font-normal font-mono tabular-nums text-[#06141B] dark:text-[#CCD0CF]">
                {formatNumber(stats.embedded_chunks)}
              </div>
              <div className="text-[11px] text-[#253745] dark:text-[#9BA8AB] mt-1 font-mono tabular-nums">
                {stats.unembedded_chunks > 0
                  ? `${formatNumber(stats.unembedded_chunks)} pending`
                  : "0 pending"}
              </div>
            </div>

            <div className="p-5">
              <div className="text-xs text-[#4A5C6A] dark:text-[#9BA8AB] mb-1">
                Corpus Footprint
              </div>
              <div className="text-2xl font-serif font-normal font-mono tabular-nums text-[#06141B] dark:text-[#CCD0CF]">
                {formatBytes(stats.total_size_bytes)}
              </div>
              <div className="text-[11px] text-[#253745] dark:text-[#9BA8AB] mt-1 font-mono tabular-nums">
                {stats.total_folders} {stats.total_folders === 1 ? "folder" : "folders"}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Recent Indexing History Table */}
      <div>
        <h2 className="text-[11px] font-mono uppercase tracking-widest text-[#4A5C6A] dark:text-[#9BA8AB] mb-3">
          Recent Indexing Runs
        </h2>

        {jobs.length > 0 ? (
          <div className="rounded-xl border border-[#9BA8AB] dark:border-[#253745] bg-[#D8DCDB] dark:bg-[#06141B]/55 overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-[#CCD0CF]/70 dark:bg-[#06141B] border-b border-[#9BA8AB] dark:border-[#253745] text-[#253745] dark:text-[#9BA8AB] font-medium">
                  <tr>
                    <th className="py-3 px-4">Job</th>
                    <th className="py-3 px-4">State</th>
                    <th className="py-3 px-4 text-right">Processed</th>
                    <th className="py-3 px-4 text-right">Succeeded</th>
                    <th className="py-3 px-4 text-right">Skipped</th>
                    <th className="py-3 px-4 text-right">Failed</th>
                    <th className="py-3 px-4 text-right">Started</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#9BA8AB]/60 dark:divide-[#253745] font-mono tabular-nums">
                  {jobs.map((job) => (
                    <tr
                      key={job.id}
                      className="hover:bg-[#E2E6E5]/60 dark:hover:bg-[#253745]/40 transition-colors"
                    >
                      <td className="py-3 px-4 font-medium text-[#06141B] dark:text-[#CCD0CF]">
                        #{job.id}
                      </td>
                      <td className="py-3 px-4 font-sans capitalize text-[#253745] dark:text-[#9BA8AB]">
                        {job.status.replace(/_/g, " ")}
                      </td>
                      <td className="py-3 px-4 text-right text-[#06141B] dark:text-[#CCD0CF]">
                        {job.processed_files} / {job.total_files}
                      </td>
                      <td className="py-3 px-4 text-right text-[#2d6a4f] dark:text-[#74c69d]">
                        {job.successful_files}
                      </td>
                      <td className="py-3 px-4 text-right text-[#4A5C6A] dark:text-[#9BA8AB]">
                        {job.skipped_files}
                      </td>
                      <td
                        className={`py-3 px-4 text-right ${
                          job.failed_files > 0
                            ? "text-[#9b2226] dark:text-[#f2b8b5]"
                            : "text-[#4A5C6A] dark:text-[#9BA8AB]"
                        }`}
                      >
                        {job.failed_files}
                      </td>
                      <td className="py-3 px-4 text-right text-[#4A5C6A] dark:text-[#9BA8AB] font-sans">
                        {formatRelativeTime(job.started_at)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ) : (
          <div className="p-8 text-center rounded-xl bg-[#D8DCDB] dark:bg-[#06141B]/55 border border-[#9BA8AB] dark:border-[#253745] text-xs text-[#4A5C6A] dark:text-[#9BA8AB]">
            No indexing jobs recorded yet.
          </div>
        )}
      </div>
    </div>
  );
}
