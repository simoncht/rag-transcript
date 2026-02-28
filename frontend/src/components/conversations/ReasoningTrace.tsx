"use client";

import { useState } from "react";
import { ChevronDown, ChevronUp, Lightbulb } from "lucide-react";

interface ReasoningTraceProps {
  reasoningContent: string;
  reasoningTokens?: number;
}

export function ReasoningTrace({ reasoningContent, reasoningTokens }: ReasoningTraceProps) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="mb-3">
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
      >
        <Lightbulb className="h-3.5 w-3.5" />
        <span>Show reasoning</span>
        {reasoningTokens && (
          <span className="text-[10px]">({reasoningTokens} tokens)</span>
        )}
        {expanded ? (
          <ChevronUp className="h-3 w-3" />
        ) : (
          <ChevronDown className="h-3 w-3" />
        )}
      </button>
      {expanded && (
        <div className="mt-2 rounded-lg border border-border/50 bg-muted/20 p-3 text-xs text-muted-foreground leading-relaxed whitespace-pre-wrap max-h-96 overflow-y-auto">
          {reasoningContent}
        </div>
      )}
    </div>
  );
}
