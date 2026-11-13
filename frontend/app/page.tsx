"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import { AppShell, ActiveTab } from "@/components/app-shell";
import { SearchView } from "@/components/search/search-view";
import { LibraryView } from "@/components/library/library-view";
import { IndexingView } from "@/components/indexing/indexing-view";
import { SettingsView } from "@/components/settings/settings-view";
import { SearchMode } from "@/lib/types";
import { folderApi, indexingApi } from "@/lib/api";

function normalizeFolderPath(p: string): string {
  if (!p) return "";
  return p
    .trim()
    .replace(/[\\/]+$/, "")
    .toLowerCase()
    .replace(/\\/g, "/");
}

export default function HomePage() {
  const [activeTab, setActiveTab] = useState<ActiveTab>("search");
  const [isIndexingActive, setIsIndexingActive] = useState(false);
  const [defaultMode, setDefaultMode] = useState<SearchMode>("hybrid");
  const [defaultLimit, setDefaultLimit] = useState(20);

  // Search scope selection state (lifted for seamless right-click folder targeting)
  const [selectedFolderId, setSelectedFolderId] = useState<number | null>(null);

  // Pending folder indexing notification state
  const [pendingFolderNotice, setPendingFolderNotice] = useState<{
    folderPath: string;
    folderId: number;
    error?: string | null;
  } | null>(null);

  const pendingNoticeRef = useRef(pendingFolderNotice);
  useEffect(() => {
    pendingNoticeRef.current = pendingFolderNotice;
  }, [pendingFolderNotice]);

  // Load preferences from localStorage on mount
  useEffect(() => {
    const savedMode = localStorage.getItem("omnisearch-default-mode") as SearchMode | null;
    if (savedMode && ["hybrid", "keyword", "semantic"].includes(savedMode)) {
      setDefaultMode(savedMode);
    }
    const savedLimit = localStorage.getItem("omnisearch-default-limit");
    if (savedLimit && !isNaN(Number(savedLimit))) {
      setDefaultLimit(Number(savedLimit));
    }
  }, []);

  const handleDefaultModeChange = (mode: SearchMode) => {
    setDefaultMode(mode);
    localStorage.setItem("omnisearch-default-mode", mode);
  };

  const handleDefaultLimitChange = (limit: number) => {
    setDefaultLimit(limit);
    localStorage.setItem("omnisearch-default-limit", String(limit));
  };

  /**
   * Handle incoming folder path from Windows Explorer context menu or CLI.
   */
  const handleOpenFolder = useCallback(async (folderPath: string) => {
    if (!folderPath || typeof folderPath !== "string") return;

    const trimmed = folderPath.trim();
    const normalizedTarget = normalizeFolderPath(trimmed);
    if (!normalizedTarget) return;

    try {
      // 1. Check if folder is already registered in OmniSearch library
      const res = await folderApi.list();
      const existingFolder = (res.folders || []).find(
        (f) => normalizeFolderPath(f.path) === normalizedTarget
      );

      if (existingFolder) {
        // CASE A: Folder is already in library -> Focus Search page on this folder scope immediately
        console.log("[OmniSearch] Folder already registered in library:", existingFolder.path);
        setSelectedFolderId(existingFolder.id);
        setActiveTab("search");
        return;
      }

      // CASE B: Folder is NOT in library -> Navigate to Indexing, register & start indexing
      console.log("[OmniSearch] Folder not in library, initiating indexing:", trimmed);
      setActiveTab("indexing");

      const created = await folderApi.create({
        path: trimmed,
        enabled: true,
      });

      setPendingFolderNotice({
        folderPath: created.path,
        folderId: created.id,
        error: null,
      });

      setIsIndexingActive(true);

      await folderApi.triggerIndex(created.id, {
        force_reindex: false,
        reconcile_deleted: true,
        generate_embeddings: true,
        background: true,
      });
    } catch (err) {
      console.error("[OmniSearch] Failed to handle incoming folder:", err);
      setActiveTab("indexing");
      setPendingFolderNotice({
        folderPath: trimmed,
        folderId: 0,
        error: err instanceof Error ? err.message : "Failed to register folder",
      });
    }
  }, []);

  // Monitor indexing completion for pending folder
  useEffect(() => {
    if (!pendingFolderNotice || pendingFolderNotice.folderId <= 0) return;

    let isSubscribed = true;
    const targetFolderId = pendingFolderNotice.folderId;

    const checkJobStatus = async () => {
      try {
        const statusRes = await indexingApi.getStatus();
        if (!isSubscribed) return;

        // If indexing has completed
        if (!statusRes.is_indexing) {
          // Double check folder is in library
          const listRes = await folderApi.list();
          const found = (listRes.folders || []).find((f) => f.id === targetFolderId);
          if (found && isSubscribed) {
            console.log("[OmniSearch] Indexing finished for folder:", found.path);
            setPendingFolderNotice(null);
            setSelectedFolderId(found.id);
            setActiveTab("search");
          }
        }
      } catch (err) {
        console.warn("[OmniSearch] Status check notice:", err);
      }
    };

    const timer = setInterval(checkJobStatus, 2500);
    return () => {
      isSubscribed = false;
      clearInterval(timer);
    };
  }, [pendingFolderNotice]);

  // Connect Electron desktop bridge listeners for Explorer context menu handoff
  useEffect(() => {
    if (typeof window === "undefined" || !window.omnisearch) return;

    // Check for startup folder path (cold launch)
    if (window.omnisearch.getInitialFolderPath) {
      window.omnisearch
        .getInitialFolderPath()
        .then((initialPath) => {
          if (initialPath) {
            console.log("[OmniSearch] Processing initial startup folder path:", initialPath);
            handleOpenFolder(initialPath);
          }
        })
        .catch((err) => {
          console.warn("[OmniSearch] Could not retrieve initial folder path:", err);
        });
    }

    // Subscribe to second-instance folder path broadcasts (already running instance)
    if (window.omnisearch.onOpenFolderPath) {
      const unsubscribe = window.omnisearch.onOpenFolderPath((folderPath) => {
        console.log("[OmniSearch] Processing second-instance folder path:", folderPath);
        handleOpenFolder(folderPath);
      });
      return () => {
        unsubscribe();
      };
    }
  }, [handleOpenFolder]);

  return (
    <AppShell
      activeTab={activeTab}
      onTabChange={setActiveTab}
      isIndexingActive={isIndexingActive}
    >
      {activeTab === "search" && (
        <SearchView
          onOpenLibrary={() => setActiveTab("library")}
          defaultMode={defaultMode}
          defaultLimit={defaultLimit}
          initialFolderId={selectedFolderId}
          onSelectFolderId={setSelectedFolderId}
        />
      )}

      {activeTab === "library" && (
        <LibraryView
          onTriggerIndexingSuccess={() => setIsIndexingActive(true)}
        />
      )}

      {activeTab === "indexing" && (
        <IndexingView
          onIndexingStateChange={(active) => setIsIndexingActive(active)}
          pendingFolderNotice={pendingFolderNotice}
        />
      )}

      {activeTab === "settings" && (
        <SettingsView
          defaultMode={defaultMode}
          onDefaultModeChange={handleDefaultModeChange}
          defaultLimit={defaultLimit}
          onDefaultLimitChange={handleDefaultLimitChange}
        />
      )}
    </AppShell>
  );
}
