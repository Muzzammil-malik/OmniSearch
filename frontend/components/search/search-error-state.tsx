"use client";

import React from "react";
import { RefreshCw } from "lucide-react";
import { Button } from "../ui/button";

interface SearchErrorStateProps {
  error: string;
  onRetry: () => void;
}

export function SearchErrorState({ error, onRetry }: SearchErrorStateProps) {
  return (
    <div className="py-16 px-6 text-center max-w-md mx-auto rounded-xl bg-[#D8DCDB] dark:bg-[#11212D] border border-[#9b2226]/30">
      <p className="text-[11px] font-mono uppercase tracking-widest text-[#9b2226] dark:text-[#f2b8b5] mb-1.5">
        Retrieval Error
      </p>
      <h3 className="text-lg font-serif font-medium text-[#06141B] dark:text-[#CCD0CF] mb-2">
        Unable to complete search request
      </h3>
      <p className="text-xs font-mono text-[#253745] dark:text-[#9BA8AB] mb-6 leading-relaxed break-words">
        {error}
      </p>
      <Button variant="secondary" size="sm" onClick={onRetry}>
        <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
        Retry search
      </Button>
    </div>
  );
}
