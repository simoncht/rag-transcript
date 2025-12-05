'use client';

import React from 'react';
import { ChunkReference } from '@/lib/types';
import CitationBadge from './CitationBadge';

interface MessageBubbleProps {
  text: string;
  isUser: boolean;
  citations?: ChunkReference[];
  timestamp?: Date;
  responseTime?: number;
}

/**
 * MessageBubble - Theme-aware chat message component
 * Colors and styling automatically adapt to theme tokens
 */
export default function MessageBubble({
  text,
  isUser,
  citations = [],
  timestamp,
  responseTime,
}: MessageBubbleProps) {
  const bubbleClasses = isUser
    ? 'ml-auto bg-primary-50 border-l-4 border-l-primary text-text-primary'
    : 'mr-auto bg-bg-secondary border-l-4 border-l-secondary text-text-primary';

  const maxWidth = isUser ? 'max-w-xs md:max-w-md' : 'max-w-sm md:max-w-lg';

  return (
    <div className={`flex flex-col gap-2 mb-4 ${isUser ? 'items-end' : 'items-start'}`}>
      {/* Main message bubble */}
      <div
        className={`
          ${bubbleClasses}
          ${maxWidth}
          rounded-lg p-4
          shadow-sm
          break-words
          transition-shadow duration-200 ease-smooth
          hover:shadow-md
        `}
      >
        <p className="font-body text-sm md:text-base leading-relaxed whitespace-pre-wrap">
          {text}
        </p>

        {/* Citations */}
        {citations.length > 0 && (
          <div className="flex flex-wrap gap-2 mt-3 pt-3 border-t border-border-default">
            {citations.map((citation, index) => (
              <CitationBadge
                key={`${citation.id}-${index}`}
                citation={citation}
                index={index + 1}
              />
            ))}
          </div>
        )}
      </div>

      {/* Metadata (timestamp, response time) */}
      {(timestamp || responseTime) && !isUser && (
        <div className="text-xs text-text-muted px-2">
          {responseTime && (
            <span className="mr-3">
              ⏱ {(responseTime / 1000).toFixed(1)}s
            </span>
          )}
          {timestamp && (
            <span>
              {timestamp.toLocaleTimeString([], {
                hour: '2-digit',
                minute: '2-digit',
              })}
            </span>
          )}
        </div>
      )}
    </div>
  );
}
