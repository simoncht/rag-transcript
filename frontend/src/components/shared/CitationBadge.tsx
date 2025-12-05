'use client';

import React, { useState } from 'react';
import { ChunkReference } from '@/lib/types';

interface CitationBadgeProps {
  citation: ChunkReference;
  index: number;
  onTimestampClick?: (timestamp: string) => void;
}

/**
 * CitationBadge - Inline citation with expandable detail
 * Shows relevance score and source information
 */
export default function CitationBadge({
  citation,
  index,
  onTimestampClick,
}: CitationBadgeProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  const relevancePercentage = Math.round((citation.relevance_score || 0) * 100);
  const videoTitle = citation.video_title || 'Unknown Video';
  const timestamp = citation.timestamp_display || '--:--';

  return (
    <div className="inline-block">
      {/* Badge button */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="
          inline-flex items-center gap-1
          px-3 py-1 rounded-full
          text-xs font-medium
          bg-accent-main/10
          text-accent-dark
          border border-accent-light
          hover:bg-accent-main/20
          transition-colors duration-200
          cursor-pointer
        "
        aria-label={`Citation ${index}: ${videoTitle}`}
      >
        <span className="font-semibold">[{index}]</span>
        <span className="hidden sm:inline text-text-muted">
          {relevancePercentage}%
        </span>
      </button>

      {/* Expanded detail card */}
      {isExpanded && (
        <div className="
          absolute mt-2 w-72 p-4
          bg-bg-secondary
          border border-border-default rounded-lg
          shadow-lg
          z-10
          animate-in fade-in duration-200
        ">
          {/* Header */}
          <div className="flex items-start justify-between gap-2 mb-3">
            <div className="flex-1">
              <h4 className="text-sm font-semibold text-text-primary mb-1">
                Source: {videoTitle}
              </h4>
              <p className="text-xs text-text-secondary">
                Citation {index}
              </p>
            </div>
            <button
              onClick={() => setIsExpanded(false)}
              className="
                text-text-muted hover:text-text-primary
                transition-colors
                p-1
              "
              aria-label="Close citation details"
            >
              ✕
            </button>
          </div>

          {/* Timestamp */}
          <div className="mb-3 pb-3 border-b border-border-default">
            <button
              onClick={() => {
                onTimestampClick?.(timestamp);
                setIsExpanded(false);
              }}
              className="
                inline-flex items-center gap-2
                text-sm text-primary hover:text-primary-light
                transition-colors duration-200
                font-medium
              "
            >
              <span className="text-lg">⏱</span>
              <span className="font-mono">{timestamp}</span>
              <span className="text-text-muted">→</span>
            </button>
            <p className="text-xs text-text-muted mt-1">
              Click to jump to timestamp
            </p>
          </div>

          {/* Relevance score */}
          <div className="mb-3">
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs font-medium text-text-secondary">
                Relevance
              </span>
              <span className="text-xs font-semibold text-accent-dark">
                {relevancePercentage}%
              </span>
            </div>
            <div className="w-full h-2 bg-border-default rounded-full overflow-hidden">
              <div
                className="h-full bg-accent-main transition-all duration-300"
                style={{ width: `${relevancePercentage}%` }}
              />
            </div>
          </div>

          {/* Snippet preview */}
          {citation.text_snippet && (
            <div className="mt-3 p-2 bg-bg-tertiary rounded text-xs text-text-secondary leading-relaxed border-l-2 border-accent-main">
              <p className="line-clamp-3">"{citation.text_snippet}"</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
