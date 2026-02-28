"use client";

import { useState } from "react";
import { ChevronDown, ChevronUp, Search } from "lucide-react";
import type { RetrievalMetadata } from "@/lib/types";

interface RetrievalDetailsProps {
  metadata: RetrievalMetadata;
}

export function RetrievalDetails({ metadata }: RetrievalDetailsProps) {
  const [expanded, setExpanded] = useState(false);

  const timing = metadata.timing;

  return (
    <div className="mt-1">
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-1.5 text-[11px] text-muted-foreground hover:text-foreground transition-colors"
      >
        <Search className="h-3 w-3" />
        <span>Show retrieval details</span>
        {expanded ? (
          <ChevronUp className="h-3 w-3" />
        ) : (
          <ChevronDown className="h-3 w-3" />
        )}
      </button>
      {expanded && (
        <div className="mt-2 rounded-lg border border-border/50 bg-muted/20 p-3 text-[11px] text-muted-foreground font-mono space-y-2">
          {/* Query Processing */}
          <div>
            <div className="font-semibold text-foreground/80 mb-1">Query Processing</div>
            <div className="pl-3 space-y-0.5">
              <div>Original: &quot;{metadata.original_query}&quot;</div>
              {metadata.effective_query && (
                <div>Rewritten: &quot;{metadata.effective_query}&quot;</div>
              )}
            </div>
          </div>

          {/* Search Results */}
          <div>
            <div className="font-semibold text-foreground/80 mb-1">Search Results</div>
            <div className="pl-3 space-y-0.5">
              {metadata.total_retrieved != null && (
                <div>{metadata.total_retrieved} chunks retrieved</div>
              )}
              {metadata.total_after_filter != null && (
                <div>{metadata.total_after_filter} passed relevance filter</div>
              )}
              {metadata.total_after_rerank != null && (
                <div>{metadata.total_after_rerank} after reranking</div>
              )}
              <div>{metadata.final_chunks ?? 0} final ({metadata.unique_videos ?? 0} videos)</div>
              {metadata.retrieval_type && (
                <div>Type: {metadata.retrieval_type}</div>
              )}
            </div>
          </div>

          {/* Timing */}
          {timing && (
            <div>
              <div className="font-semibold text-foreground/80 mb-1">Timing</div>
              <div className="pl-3 space-y-0.5">
                {timing.retrieval_ms != null && (
                  <div>Retrieval: {(timing.retrieval_ms / 1000).toFixed(1)}s</div>
                )}
                {timing.llm_ms != null && (
                  <div>LLM generation: {(timing.llm_ms / 1000).toFixed(1)}s</div>
                )}
                {timing.total_ms != null && (
                  <div className="font-medium">Total: {(timing.total_ms / 1000).toFixed(1)}s</div>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
