"use client";

import { useState, useMemo, useCallback, memo } from "react";
import ReactMarkdown from "react-markdown";
import type { Message, ChunkReference } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn, formatMessageTime } from "@/lib/utils";
import { ConfidenceBadge } from "@/components/conversations/ConfidenceBadge";
import { ReasoningTrace } from "@/components/conversations/ReasoningTrace";
import { RetrievalDetails } from "@/components/conversations/RetrievalDetails";
import { FollowUpQuestions } from "@/components/conversations/FollowUpQuestions";
import {
  Video,
  FileText,
  ChevronDown,
  ChevronUp,
  Copy,
  Check,
} from "lucide-react";
import {
  MARKDOWN_STATIC_COMPONENTS,
  REMARK_PLUGINS,
  linkifySourceMentions,
  groupSourcesByVideo,
} from "./chat-utils";

export interface MessageItemProps {
  message: Message & { chunk_references?: ChunkReference[] };
  highlightedSourceId: string | null;
  copiedId: string | null;
  onCitationClick: (messageId: string, rank?: number) => void;
  onCopy: (messageId: string, content: string) => void;
  onFollowUpClick?: (question: string) => void;
}

export const MessageItem = memo<MessageItemProps>(({ message, highlightedSourceId, copiedId, onCitationClick, onCopy, onFollowUpClick }) => {
  const [sourcesExpanded, setSourcesExpanded] = useState(false);
  const isSystem = message.role === "system";
  const isUser = message.role === "user";
  const isAssistant = message.role === "assistant";
  const chunkReferences = message.chunk_references;

  const sortedSources = useMemo(
    () =>
      chunkReferences
        ? [...chunkReferences].sort(
            (a, b) => (a.rank ?? 0) - (b.rank ?? 0)
          )
        : [],
    [chunkReferences]
  );

  // Group sources by video for multi-video display
  const groupedSources = useMemo(
    () => groupSourcesByVideo(sortedSources),
    [sortedSources]
  );
  const totalVideos = groupedSources.length;
  const totalSources = sortedSources.length;

  const resolveJumpUrl = useCallback((chunk: ChunkReference) => {
    if (chunk.jump_url) return chunk.jump_url;
    // For documents, build internal viewer URL
    if (chunk.content_type && chunk.content_type !== "youtube") {
      const page = chunk.page_number;
      if (page) return `/documents/${chunk.video_id}?page=${page}`;
      return `/documents/${chunk.video_id}`;
    }
    // For videos, build YouTube timestamp URL
    const base = chunk.video_url;
    if (!base) return undefined;
    const start = Math.max(0, Math.floor(chunk.start_timestamp || 0));
    const separator = base.includes("?") ? "&" : "?";
    return `${base}${separator}t=${start}`;
  }, []);

  // Memoize markdown content processing to avoid regex on every render
  const markdownContent = useMemo(
    () =>
      isAssistant
        ? linkifySourceMentions(message.content, message.id, chunkReferences)
        : message.content,
    [isAssistant, message.content, message.id, chunkReferences]
  );

  const handleSourceClick = useCallback(
    (rank?: number) => {
      if (!rank) return;
      // Expand sources first if collapsed
      setSourcesExpanded(true);
      // Use setTimeout to allow DOM to update before scrolling
      setTimeout(() => {
        onCitationClick(message.id, rank);
      }, 50);
    },
    [message.id, onCitationClick]
  );

  // Performance: Memoize markdown components - combine static with dynamic anchor
  const markdownComponents = useMemo(() => ({
    ...MARKDOWN_STATIC_COMPONENTS,
    a: ({ href, children, ...props }: any) => {
      const isCitation = href?.startsWith("#source-");
      const rankMatch = href?.match(/-(\d+)$/);
      const rankNumber = rankMatch?.[1] ? parseInt(rankMatch[1], 10) : undefined;
      return (
        <a
          {...props}
          href={href}
          className={cn(
            "underline-offset-2",
            isCitation
              ? "text-muted-foreground/70 text-[10px] align-super font-normal no-underline hover:text-primary cursor-pointer"
              : "text-primary hover:underline"
          )}
          onClick={(event: React.MouseEvent) => {
            if (isCitation) {
              event.preventDefault();
              handleSourceClick(rankNumber);
            }
          }}
        >
          {children}
        </a>
      );
    },
  }), [handleSourceClick]);

  if (isSystem) {
    return (
      <div key={message.id} className="flex w-full justify-center">
        <div className="flex max-w-[90%] flex-col items-center gap-1">
          <span className="text-[10px] text-muted-foreground">
            {formatMessageTime(message.created_at)}
          </span>
          <div className="rounded-full border border-border bg-muted/40 px-4 py-1.5 text-xs text-muted-foreground">
            {message.content}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div
      key={message.id}
      className={cn("flex w-full", isUser ? "justify-end" : "justify-start")}
    >
      <div
        className={cn(
          "flex w-full max-w-[90%] flex-col gap-3",
          isUser ? "items-end text-right" : "items-start text-left",
        )}
      >
        {/* Message header */}
        <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
          <span>{formatMessageTime(message.created_at)}</span>
        </div>

        {isUser ? (
          <div className="flex w-full justify-end">
            <p className="inline-flex max-w-[75%] rounded-2xl bg-primary/10 px-5 py-3 text-base leading-relaxed text-foreground shadow-lg break-words text-right">
              {message.content}
            </p>
          </div>
        ) : (
          <div className="w-full rounded-2xl border border-border bg-muted/40 p-4 shadow-sm">
            {/* Confidence badge */}
            {message.confidence && (
              <ConfidenceBadge confidence={message.confidence} />
            )}
            {/* Reasoning trace (DeepSeek Reasoner only) */}
            {message.reasoning_content && (
              <ReasoningTrace
                reasoningContent={message.reasoning_content}
                reasoningTokens={message.reasoning_tokens}
              />
            )}
            {/* Performance: Using memoized components and plugins */}
            <ReactMarkdown
              className="prose prose-base leading-relaxed max-w-full break-words dark:prose-invert"
              remarkPlugins={REMARK_PLUGINS}
              components={markdownComponents}
            >
              {markdownContent}
            </ReactMarkdown>
          </div>
        )}

        {/* Metadata for assistant messages */}
        {isAssistant && (
          <>
            <div className="flex flex-wrap items-center gap-3 text-[11px] text-muted-foreground">
              {message.response_time_seconds != null && (
                <span>{message.response_time_seconds.toFixed(1)}s</span>
              )}
              {message.chunks_retrieved_count != null && (
                <span>
                  {message.chunks_retrieved_count} source
                  {message.chunks_retrieved_count !== 1 ? "s" : ""}
                </span>
              )}
              {message.token_count != null && (
                <span>{message.token_count} tokens</span>
              )}
              <button
                onClick={() => onCopy(message.id, message.content)}
                className="inline-flex items-center gap-1 hover:text-foreground transition-colors"
              >
                {copiedId === message.id ? (
                  <><Check className="h-3 w-3" /> Copied</>
                ) : (
                  <><Copy className="h-3 w-3" /> Copy</>
                )}
              </button>
            </div>
            {/* Retrieval transparency toggle */}
            {message.retrieval_metadata && (
              <RetrievalDetails metadata={message.retrieval_metadata} />
            )}
            {/* Follow-up questions */}
            {message.followup_questions && message.followup_questions.length > 0 && onFollowUpClick && (
              <FollowUpQuestions
                questions={message.followup_questions}
                onQuestionClick={onFollowUpClick}
              />
            )}
          </>
        )}

        {/* Sources section - collapsible, grouped by video for multi-video conversations */}
        {isAssistant && totalSources > 0 && (
          <div className="rounded-lg border border-border bg-muted/30">
            {/* Clickable header to toggle sources */}
            <button
              type="button"
              onClick={() => setSourcesExpanded(!sourcesExpanded)}
              className="flex w-full items-center justify-between px-3 py-2 text-left hover:bg-muted/50 transition-colors rounded-lg"
            >
              <p className="text-xs font-medium">
                Sources ({totalSources}{totalVideos > 1 ? ` from ${totalVideos} sources` : ""})
              </p>
              {sourcesExpanded ? (
                <ChevronUp className="h-4 w-4 text-muted-foreground" />
              ) : (
                <ChevronDown className="h-4 w-4 text-muted-foreground" />
              )}
            </button>

            {/* Collapsible sources content */}
            {sourcesExpanded && (
              <div className="space-y-4 px-3 pb-3">
                {groupedSources.map((group) => (
                  <div key={group.videoId} className="space-y-2">
                    {/* Source group header - only shown when multiple sources */}
                    {totalVideos > 1 && (
                      <div className="flex items-center gap-2 border-b border-border/50 pb-1.5">
                        {group.contentType && group.contentType !== "youtube" ? (
                          <FileText className="h-3.5 w-3.5 text-muted-foreground" />
                        ) : (
                          <Video className="h-3.5 w-3.5 text-muted-foreground" />
                        )}
                        <span className="text-xs font-medium">{group.videoTitle}</span>
                        {group.channelName && group.contentType === "youtube" && (
                          <span className="text-[10px] text-muted-foreground">
                            {group.channelName}
                          </span>
                        )}
                        {group.contentType && group.contentType !== "youtube" && (
                          <span className="text-[10px] text-muted-foreground uppercase">
                            {group.contentType}
                          </span>
                        )}
                        <span className="ml-auto text-[10px] text-muted-foreground">
                          {group.sources.length} source{group.sources.length !== 1 ? "s" : ""}
                        </span>
                      </div>
                    )}

                    {/* Individual sources within this video group */}
                    <div className="space-y-2">
                      {group.sources.map((chunk, idx) => {
                        const chunkRank = chunk.rank ?? idx + 1;
                        const sourceAnchorId = `source-${message.id}-${chunkRank}`;
                        const jumpUrl = resolveJumpUrl(chunk);
                        const relevancePct = Math.round((chunk.relevance_score ?? 0) * 100);
                        return (
                          <div
                            key={`${chunk.chunk_id}-${chunkRank}`}
                            id={sourceAnchorId}
                            className={cn(
                              "rounded-md border bg-background/60 px-3 py-2 text-xs transition-shadow",
                              highlightedSourceId === sourceAnchorId && "ring-2 ring-primary/60 bg-primary/5"
                            )}
                          >
                            <div className="mb-1 flex flex-wrap items-center gap-2">
                              <Badge variant="outline" className="text-[10px] uppercase">
                                [{chunkRank}]
                              </Badge>
                              <span className="text-muted-foreground">
                                {chunk.location_display || chunk.timestamp_display}
                              </span>
                              <span className="ml-auto text-[10px] text-muted-foreground">
                                {relevancePct}% match
                              </span>
                            </div>
                            {/* Contextual metadata - content-type-aware */}
                            {chunk.content_type && chunk.content_type !== "youtube" ? (
                              chunk.section_heading && (
                                <div className="mb-1.5 flex flex-wrap items-center gap-1.5 text-[10px] text-muted-foreground">
                                  <span className="flex items-center gap-1">
                                    <span className="opacity-60">Section:</span>
                                    {chunk.section_heading}
                                  </span>
                                </div>
                              )
                            ) : (chunk.chapter_title || (chunk.speakers && chunk.speakers.length > 0) || (totalVideos === 1 && chunk.channel_name)) ? (
                              <div className="mb-1.5 flex flex-wrap items-center gap-1.5 text-[10px] text-muted-foreground">
                                {totalVideos === 1 && chunk.channel_name && (
                                  <span className="flex items-center gap-1">
                                    <span className="opacity-60">Channel:</span>
                                    {chunk.channel_name}
                                  </span>
                                )}
                                {chunk.chapter_title && (
                                  <span className="flex items-center gap-1">
                                    <span className="opacity-60">Chapter:</span>
                                    {chunk.chapter_title}
                                  </span>
                                )}
                                {chunk.speakers && chunk.speakers.length > 0 && (
                                  <span className="flex items-center gap-1">
                                    <span className="opacity-60">Speaker:</span>
                                    {chunk.speakers.join(', ')}
                                  </span>
                                )}
                              </div>
                            ) : null}
                            <p className="text-[11px] text-muted-foreground leading-relaxed">
                              {chunk.text_snippet}
                            </p>
                            <div className="mt-2 flex flex-wrap items-center gap-2">
                              {jumpUrl && (
                                chunk.content_type && chunk.content_type !== "youtube" ? (
                                  <Button asChild variant="outline" size="sm" className="gap-1 text-[11px]">
                                    <a href={jumpUrl}>
                                      <FileText className="h-3.5 w-3.5" />
                                      View in document
                                    </a>
                                  </Button>
                                ) : (
                                  <Button asChild variant="outline" size="sm" className="gap-1 text-[11px]">
                                    <a href={jumpUrl} target="_blank" rel="noopener noreferrer">
                                      <Video className="h-3.5 w-3.5" />
                                      Jump to video
                                    </a>
                                  </Button>
                                )
                              )}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
});

MessageItem.displayName = "MessageItem";
