"use client";

import { memo } from "react";
import ReactMarkdown from "react-markdown";
import { Loader2 } from "lucide-react";
import { MARKDOWN_STATIC_COMPONENTS, REMARK_PLUGINS } from "./chat-utils";

export interface StreamingMessageProps {
  content: string;
  isStreaming: boolean;
  elapsedTime: number | null;
  statusStage?: string | null;
  statusMessage?: string | null;
}

export const StreamingMessage = memo<StreamingMessageProps>(
  ({ content, isStreaming, elapsedTime, statusStage, statusMessage }) => (
    <div className="flex w-full justify-start">
      <div className="flex w-full max-w-[90%] flex-col gap-3 items-start text-left">
        {/* Header with timing info */}
        <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
          {isStreaming && !content && statusMessage && (
            <span className="flex items-center gap-1.5">
              <Loader2 className="h-3 w-3 animate-spin" />
              {statusMessage}
            </span>
          )}
          {isStreaming && !content && !statusMessage && (
            <span className="flex items-center gap-1.5">
              <Loader2 className="h-3 w-3 animate-spin" />
              Thinking...
            </span>
          )}
          {isStreaming && content && (
            <span className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-primary animate-pulse" />
              Responding...
            </span>
          )}
          {elapsedTime !== null && elapsedTime > 0 && (
            <span>{elapsedTime.toFixed(1)}s</span>
          )}
        </div>

        {/* Pipeline progress indicator (pre-content) */}
        {isStreaming && !content && statusStage && (
          <div className="flex items-center gap-3 text-xs text-muted-foreground px-1">
            <span className={statusStage === "analyzing" ? "text-primary font-medium" : statusStage === "searching" || statusStage === "generating" ? "text-muted-foreground/60" : ""}>
              Analyze
            </span>
            <span className="text-muted-foreground/30">&rarr;</span>
            <span className={statusStage === "searching" ? "text-primary font-medium" : statusStage === "generating" ? "text-muted-foreground/60" : "text-muted-foreground/40"}>
              Search
            </span>
            <span className="text-muted-foreground/30">&rarr;</span>
            <span className={statusStage === "generating" ? "text-primary font-medium" : "text-muted-foreground/40"}>
              Generate
            </span>
          </div>
        )}

        {/* Content area */}
        <div className="w-full rounded-2xl border border-border bg-muted/40 p-4 shadow-sm">
          {content ? (
            <div className="relative">
              <ReactMarkdown
                className="prose prose-base leading-relaxed max-w-full break-words dark:prose-invert"
                remarkPlugins={REMARK_PLUGINS}
                components={MARKDOWN_STATIC_COMPONENTS}
              >
                {content}
              </ReactMarkdown>
              {/* Blinking cursor at the end while streaming */}
              {isStreaming && (
                <span className="inline-block w-2 h-4 bg-primary/60 animate-pulse ml-0.5 align-text-bottom" />
              )}
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <div className="h-4 w-4 rounded bg-muted animate-pulse" />
              <div className="h-4 w-32 rounded bg-muted animate-pulse" />
            </div>
          )}
        </div>

        {/* Sources placeholder */}
        {isStreaming && (
          <span className="text-[11px] text-muted-foreground">
            Sources will appear when complete...
          </span>
        )}
      </div>
    </div>
  )
);

StreamingMessage.displayName = "StreamingMessage";
