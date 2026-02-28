"use client";

import type { ConfidenceInfo } from "@/lib/types";

interface ConfidenceBadgeProps {
  confidence: ConfidenceInfo;
}

const CONFIDENCE_CONFIG = {
  strong: {
    color: "bg-green-500",
    label: "Strong confidence",
    description: (c: ConfidenceInfo) =>
      `${c.chunk_count} sources from ${c.unique_videos} video${c.unique_videos !== 1 ? "s" : ""}, avg relevance ${Math.round(c.avg_relevance * 100)}%`,
  },
  moderate: {
    color: "bg-yellow-500",
    label: "Moderate confidence",
    description: (c: ConfidenceInfo) =>
      `${c.chunk_count} source${c.chunk_count !== 1 ? "s" : ""}, avg relevance ${Math.round(c.avg_relevance * 100)}%`,
  },
  limited: {
    color: "bg-orange-500",
    label: "Limited sources",
    description: (c: ConfidenceInfo) =>
      `${c.chunk_count} source${c.chunk_count !== 1 ? "s" : ""}, avg relevance ${Math.round(c.avg_relevance * 100)}%, answer may be incomplete`,
  },
};

export function ConfidenceBadge({ confidence }: ConfidenceBadgeProps) {
  const config = CONFIDENCE_CONFIG[confidence.level] || CONFIDENCE_CONFIG.limited;

  return (
    <div className="flex items-center gap-2 text-xs text-muted-foreground mb-2">
      <span className={`inline-block h-2 w-2 rounded-full ${config.color}`} />
      <span className="font-medium">{config.label}</span>
      <span className="text-[10px]">{config.description(confidence)}</span>
    </div>
  );
}
