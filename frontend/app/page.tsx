"use client";

import React, { useState, useEffect } from "react";
import { AppShell, ActiveTab } from "@/components/app-shell";
import { SearchView } from "@/components/search/search-view";
import { LibraryView } from "@/components/library/library-view";
import { IndexingView } from "@/components/indexing/indexing-view";
import { SettingsView } from "@/components/settings/settings-view";
import { SearchMode } from "@/lib/types";

export default function HomePage() {
  const [activeTab, setActiveTab] = useState<ActiveTab>("search");
  const [isIndexingActive, setIsIndexingActive] = useState(false);
  const [defaultMode, setDefaultMode] = useState<SearchMode>("hybrid");
  const [defaultLimit, setDefaultLimit] = useState(20);

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
