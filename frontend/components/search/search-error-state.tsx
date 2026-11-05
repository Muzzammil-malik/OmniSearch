"use client";

import React from "react";
import { AlertCircle, RefreshCw } from "lucide-react";
import { Button } from "../ui/button";

interface SearchErrorStateProps {
  error: string;
  onRetry: () => void;
}

export function SearchErrorState({ error, onRetry }: SearchErrorStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-20 px-4 text-center max-w-md mx-auto">
      <div className="w-12 h-12 rounded-2xl bg-red-500/10 border border-red-500/20 flex items-center justify-center text-red-500 mb-4">
        <AlertCircle className="w-6 h-6 stroke-[1.75]" />
      </div>
      <h3 className="text-base font-semibold text-slate-900 dark:text-slate-100 mb-1">
        Search Request Failed
      </h3>
      <p className="text-sm text-slate-500 dark:text-slate-400 mb-6 leading-relaxed break-words font-mono text-xs max-w-sm">
        {error}
      </p>
      <Button variant="secondary" size="sm" onClick={onRetry}>
        <RefreshCw className="w-4 h-4 mr-2" />
        Retry Search
      </Button>
    </div>
  );
}

