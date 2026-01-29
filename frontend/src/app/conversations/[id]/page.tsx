"use client";

/**
 * Conversations Page - Performance Optimized
 *
 * Performance Fix: Parallel auth + data fetching
 * Before: Sequential auth → 3 queries (5s total)
 * After: All parallel (~1-2s)
 */

import { useEffect, useRef, useState, useMemo, useCallback, memo } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useAuth, useAuthState, createParallelQueryFn } from "@/lib/auth";
import { apiClient } from "@/lib/api/client";
import { subscriptionsApi } from "@/lib/api/subscriptions";
import QuotaDisplay from "@/components/subscription/QuotaDisplay";
import type { QuotaUsage } from "@/lib/types";
import { conversationsApi } from "@/lib/api/conversations";
import { insightsApi } from "@/lib/api/insights";
import { videosApi } from "@/lib/api/videos";
import { useStreamingMessage } from "@/hooks/useStreamingMessage";
import type {
  ConversationWithMessages,
  Message,
  ChunkReference,
  ConversationInsightsResponse,
} from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Sheet,
  SheetContent,
  SheetTrigger,
} from "@/components/ui/sheet";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn, formatMessageTime } from "@/lib/utils";
import { formatDistanceToNow } from "date-fns";
import { ConversationInsightMap } from "@/components/insights/ConversationInsightMap";
import {
  ArrowLeft,
  Loader2,
  MessageCircle,
  MessageSquare,
  Menu,
  Plus,
  Video,
  Folder,
  Network,
  RotateCcw,
  Maximize2,
  Minimize2,
  X,
  LogOut,
  Shield,
  User,
  Settings,
  PanelRightClose,
  PanelRightOpen,
  Info,
  Square,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import Link from "next/link";
import { ThemeToggle } from "@/components/layout/ThemeToggle";
import type { Conversation } from "@/lib/types";

const EMPTY_MESSAGES: Message[] = [];

// Performance: Memoized markdown components to avoid recreation on every render
// Static components that don't depend on props
const MARKDOWN_STATIC_COMPONENTS = {
  h1: ({ node, ...props }: any) => (
    <h1 className="mt-6 mb-3 text-base font-semibold leading-tight" {...props} />
  ),
  h2: ({ node, ...props }: any) => (
    <h2 className="mt-6 mb-3 text-base font-semibold leading-tight" {...props} />
  ),
  h3: ({ node, ...props }: any) => (
    <h3 className="mt-6 mb-3 text-base font-semibold leading-tight" {...props} />
  ),
  p: ({ node, ...props }: any) => (
    <p className="my-4 text-base leading-relaxed" {...props} />
  ),
  ul: ({ node, ...props }: any) => (
    <ul className="my-4 list-disc space-y-2 pl-5 leading-relaxed text-base" {...props} />
  ),
  ol: ({ node, ...props }: any) => (
    <ol className="my-4 list-decimal space-y-2 pl-5 leading-relaxed text-base" {...props} />
  ),
  li: ({ node, ...props }: any) => (
    <li className="leading-relaxed text-base" {...props} />
  ),
  table: ({ node, ...props }: any) => (
    <div className="my-5 overflow-hidden rounded-lg border border-border">
      <table className="w-full table-auto border-collapse text-sm" {...props} />
    </div>
  ),
  thead: ({ node, ...props }: any) => (
    <thead className="bg-muted/70" {...props} />
  ),
  tbody: ({ node, ...props }: any) => (
    <tbody className="divide-y divide-border" {...props} />
  ),
  tr: ({ node, ...props }: any) => (
    <tr className="divide-x divide-border" {...props} />
  ),
  th: ({ node, ...props }: any) => (
    <th className="px-3 py-2 text-left font-semibold text-foreground align-top whitespace-pre-wrap" {...props} />
  ),
  td: ({ node, ...props }: any) => (
    <td className="px-3 py-2 align-top text-foreground whitespace-pre-wrap" {...props} />
  ),
  hr: () => null,
};

// Performance: Pre-configured remark plugins array to avoid recreation
const REMARK_PLUGINS = [remarkGfm];

const MODEL_OPTIONS = [
  {
    id: "deepseek-chat",
    label: "Chat",
    description: "Fast responses (Free tier)",
    tooltip: "Fast & efficient. Best for quick questions, finding quotes, and simple summaries.",
  },
  {
    id: "deepseek-reasoner",
    label: "Reasoner",
    description: "Advanced reasoning (Pro tier)",
    tooltip: "Thinks before answering. Best for complex analysis, comparing sources, and finding patterns.",
  },
];

const MODE_OPTIONS = [
  {
    id: "summarize",
    label: "Summarize",
    helper: "Highlight core ideas concisely",
  },
  {
    id: "deep_dive",
    label: "Deep Dive",
    helper: "Explain layers, implications, patterns",
  },
  {
    id: "compare_sources",
    label: "Compare Sources",
    helper: "Contrast speakers and highlight agreements",
  },
  // Future modes - will be enabled after testing:
  // { id: "timeline", label: "Timeline", helper: "Sequence events chronologically" },
  // { id: "extract_actions", label: "Extract Actions", helper: "List concrete decisions and owners" },
  // { id: "quiz_me", label: "Quiz Me", helper: "Pose knowledge-check questions" },
];
type ModeId = (typeof MODE_OPTIONS)[number]["id"];

// Helper function: linkify source mentions in markdown content
// Converts "Source N" and "[N]" to clickable footnote-style citations
const linkifySourceMentions = (
  content: string,
  messageId: string,
  chunkRefs?: ChunkReference[],
) => {
  // First, handle explicit "Source N" mentions (legacy format)
  let result = content.replace(/Source (\d+)/g, (_match, srcNumber) => {
    const rank = Number(srcNumber?.trim());
    if (!chunkRefs || chunkRefs.length === 0 || Number.isNaN(rank)) {
      return `[${srcNumber}]`;
    }
    return `[[${rank}]](#source-${messageId}-${rank})`;
  });

  // Then, handle footnote-style [N] citations (new format from updated prompt)
  // Match [N] but not [[N]] (which we just created above) or [text](url) markdown links
  result = result.replace(/(?<!\[)\[(\d+)\](?!\()/g, (_match, srcNumber) => {
    const rank = Number(srcNumber?.trim());
    if (!chunkRefs || chunkRefs.length === 0 || Number.isNaN(rank)) {
      return `[${srcNumber}]`;
    }
    return `[[${rank}]](#source-${messageId}-${rank})`;
  });

  return result;
};

// Video grouping for multi-video conversations
interface GroupedSources {
  videoId: string;
  videoTitle: string;
  channelName?: string | null;
  sources: ChunkReference[];
}

const groupSourcesByVideo = (sources: ChunkReference[]): GroupedSources[] => {
  const grouped = new Map<string, GroupedSources>();

  for (const source of sources) {
    const existing = grouped.get(source.video_id);
    if (existing) {
      existing.sources.push(source);
    } else {
      grouped.set(source.video_id, {
        videoId: source.video_id,
        videoTitle: source.video_title,
        channelName: source.channel_name,
        sources: [source],
      });
    }
  }

  // Sort groups by the best-ranked source in each group
  return Array.from(grouped.values()).sort(
    (a, b) => (a.sources[0]?.rank ?? 0) - (b.sources[0]?.rank ?? 0)
  );
};

// Memoized Message Item Component
// Prevents re-rendering when parent state changes (e.g., typing in input box)
interface MessageItemProps {
  message: Message & { chunk_references?: ChunkReference[] };
  highlightedSourceId: string | null;
  onCitationClick: (messageId: string, rank?: number) => void;
}

const MessageItem = memo<MessageItemProps>(({ message, highlightedSourceId, onCitationClick }) => {
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
          </div>
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
                Sources ({totalSources}{totalVideos > 1 ? ` from ${totalVideos} videos` : ""})
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
                    {/* Video group header - only shown when multiple videos */}
                    {totalVideos > 1 && (
                      <div className="flex items-center gap-2 border-b border-border/50 pb-1.5">
                        <Video className="h-3.5 w-3.5 text-muted-foreground" />
                        <span className="text-xs font-medium">{group.videoTitle}</span>
                        {group.channelName && (
                          <span className="text-[10px] text-muted-foreground">
                            {group.channelName}
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
                              <span className="text-muted-foreground">{chunk.timestamp_display}</span>
                              <span className="ml-auto text-[10px] text-muted-foreground">
                                {relevancePct}% match
                              </span>
                            </div>
                            {/* Contextual metadata - chapter and speakers (channel shown in group header for multi-video) */}
                            {(chunk.chapter_title || (chunk.speakers && chunk.speakers.length > 0) || (totalVideos === 1 && chunk.channel_name)) && (
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
                            )}
                            <p className="text-[11px] text-muted-foreground leading-relaxed">
                              {chunk.text_snippet}
                            </p>
                            <div className="mt-2 flex flex-wrap items-center gap-2">
                              {jumpUrl && (
                                <Button asChild variant="outline" size="sm" className="gap-1 text-[11px]">
                                  <a href={jumpUrl} target="_blank" rel="noopener noreferrer">
                                    <Video className="h-3.5 w-3.5" />
                                    Jump to video
                                  </a>
                                </Button>
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

// StreamingMessage component - displays assistant response as it streams
interface StreamingMessageProps {
  content: string;
  isStreaming: boolean;
  elapsedTime: number | null;
}

const StreamingMessage = memo<StreamingMessageProps>(
  ({ content, isStreaming, elapsedTime }) => (
    <div className="flex w-full justify-start">
      <div className="flex w-full max-w-[90%] flex-col gap-3 items-start text-left">
        {/* Header with timing info */}
        <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
          {isStreaming && !content && (
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

export default function ConversationDetailPage() {
  const params = useParams();
  const router = useRouter();
  const conversationId = Array.isArray(params?.id) ? params.id[0] : (params?.id as string | undefined);
  const authProvider = useAuth();
  const authState = authProvider.getState();
  const isAuthenticated = authState.isAuthenticated;

  const queryClient = useQueryClient();
  const [messageText, setMessageText] = useState("");
  const [isAutoScrollEnabled, setIsAutoScrollEnabled] = useState(true);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [contextPanelOpen, setContextPanelOpen] = useState(true);
  const [sourcesSheetOpen, setSourcesSheetOpen] = useState(false);
  const [insightsDialogOpen, setInsightsDialogOpen] = useState(false);
  const [insightsDialogMaximized, setInsightsDialogMaximized] = useState(false);
  const [highlightedSourceId, setHighlightedSourceId] = useState<string | null>(null);
  const [sendError, setSendError] = useState<string | null>(null);
  const [sourcesUpdateError, setSourcesUpdateError] = useState<string | null>(null);
  const [selectedModelId, setSelectedModelId] = useState<string>("deepseek-chat");
  const [selectedMode, setSelectedMode] = useState<ModeId>(MODE_OPTIONS[0].id);
  const [isAdminBackend, setIsAdminBackend] = useState<boolean | null>(null);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const scrollContainerRef = useRef<HTMLDivElement | null>(null);
  const prevMessageCountRef = useRef<number>(0);

  // Get user info for sidebar display
  const { user } = useAuthState();
  const displayName = user?.displayName || user?.email;
  const email = user?.email;

  // Check if user is admin (stored in auth metadata)
  const isAdmin = user?.metadata?.is_superuser === true;
  const hasAdminAccess = isAdmin || isAdminBackend === true;

  // Streaming message hook for real-time chat responses
  const {
    isStreaming,
    content: streamingContent,
    sources: streamingSources,
    error: streamingError,
    elapsedTime,
    sendMessage: sendStreamingMessage,
    cancelStream,
  } = useStreamingMessage(conversationId || "");

  const handleLogout = () => {
    authProvider.signOut("/sign-in");
  };

  // Fetch admin status from backend
  useEffect(() => {
    if (!user) {
      setIsAdminBackend(false);
      return;
    }

    let isMounted = true;

    const fetchAdminStatus = async () => {
      try {
        const response = await apiClient.get("/auth/me");
        if (isMounted) {
          setIsAdminBackend(Boolean(response.data?.is_superuser));
        }
      } catch {
        if (isMounted) {
          setIsAdminBackend(false);
        }
      }
    };

    fetchAdminStatus();

    return () => {
      isMounted = false;
    };
  }, [user?.id]);

  // Performance: Parallel auth + data fetch - no blocking
  const { data: conversationsData } = useQuery({
    queryKey: ["conversations"],
    queryFn: createParallelQueryFn(authProvider, () => conversationsApi.list()),
    refetchInterval: false, // Disabled - invalidate on mutation instead
    staleTime: 5 * 60 * 1000, // 5 minutes - data rarely changes
    gcTime: 10 * 60 * 1000, // Keep in cache for 10 minutes
    enabled: isAuthenticated,
  });

  const conversations = conversationsData?.conversations ?? [];

  // Fetch quota for sidebar display
  const { data: quota } = useQuery<QuotaUsage>({
    queryKey: ["subscription-quota"],
    queryFn: subscriptionsApi.getQuota,
    enabled: isAuthenticated,
    staleTime: 60 * 1000, // 60 seconds
    refetchInterval: 120 * 1000, // Refetch every 2 minutes
  });

  // Performance: Parallel fetch with longer cache
  const {
    data: conversation,
    isLoading,
    isError,
  } = useQuery<ConversationWithMessages>({
    queryKey: ["conversation", conversationId],
    queryFn: createParallelQueryFn(authProvider, () =>
      conversationsApi.get(conversationId as string)
    ),
    enabled: isAuthenticated && !!conversationId,
    refetchInterval: false, // Disabled - only refetch on mutation success
    staleTime: 2 * 60 * 1000, // 2 minutes - optimistic updates handle new messages
    gcTime: 5 * 60 * 1000, // Keep in cache for 5 minutes
  });

  const messages = useMemo(() => conversation?.messages ?? EMPTY_MESSAGES, [conversation?.messages]);

  // Helper function to scroll to bottom of messages container
  const scrollToBottom = useCallback((behavior: ScrollBehavior = "smooth") => {
    const container = scrollContainerRef.current;
    if (container) {
      container.scrollTo({ top: container.scrollHeight, behavior });
    }
  }, []);

  // Auto-scroll when new messages arrive
  useEffect(() => {
    const nextNonSystemLength = messages.filter((m) => m.role !== "system").length;
    if (isAutoScrollEnabled && nextNonSystemLength > prevMessageCountRef.current) {
      scrollToBottom("smooth");
    }
    prevMessageCountRef.current = nextNonSystemLength;
  }, [messages, isAutoScrollEnabled, scrollToBottom]);

  // Auto-scroll during streaming (when content updates)
  useEffect(() => {
    if (isStreaming && isAutoScrollEnabled && streamingContent) {
      scrollToBottom("smooth");
    }
  }, [isStreaming, streamingContent, isAutoScrollEnabled, scrollToBottom]);

  // Performance: Parallel fetch for sources
  const { data: sourcesData, isLoading: sourcesLoading } = useQuery({
    queryKey: ["conversation", conversationId, "sources"],
    queryFn: createParallelQueryFn(authProvider, () =>
      conversationsApi.getSources(conversationId as string)
    ),
    enabled: isAuthenticated && !!conversationId,
    refetchInterval: false, // Disabled - sources don't change during chat
    staleTime: 5 * 60 * 1000, // 5 minutes - sources rarely change
    gcTime: 10 * 60 * 1000, // Keep in cache for 10 minutes
  });

  // Performance: Parallel fetch for insights
  const {
    data: insightsData,
    isLoading: insightsLoading,
    isError: insightsError,
  } = useQuery<ConversationInsightsResponse>({
    queryKey: ["conversation-insights", conversationId],
    queryFn: createParallelQueryFn(authProvider, () =>
      insightsApi.getInsights(conversationId as string)
    ),
    enabled: isAuthenticated && insightsDialogOpen && !!conversationId,
    staleTime: 300000, // 5 minutes
  });

  const regenerateInsightsMutation = useMutation({
    mutationFn: async () => {
      if (!conversationId) {
        throw new Error("Missing conversationId");
      }
      return insightsApi.getInsights(conversationId as string, true);
    },
    onSuccess: (data) => {
      queryClient.setQueryData(["conversation-insights", conversationId], data);
    },
  });


  const updateSourcesMutation = useMutation({
    mutationFn: (payload: { selected_video_ids?: string[]; add_video_ids?: string[] }) =>
      conversationsApi.updateSources(conversationId as string, payload),
    onMutate: () => {
      setSourcesUpdateError(null);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["conversation", conversationId, "sources"] });
      queryClient.invalidateQueries({ queryKey: ["conversation", conversationId] });
      queryClient.invalidateQueries({ queryKey: ["conversations"] });
    },
    onError: (error: any) => {
      const detail =
        error?.response?.data?.detail ||
        (error?.message === "Network Error" ? "Network error" : null);
      setSourcesUpdateError(detail || "Unable to update sources. Please try again.");
    },
  });

  const reprocessVideoMutation = useMutation({
    mutationFn: (videoId: string) => videosApi.reprocess(videoId),
    onSuccess: (data) => {
      setSourcesUpdateError(data.message);
      queryClient.invalidateQueries({ queryKey: ["conversation", conversationId, "sources"] });
      queryClient.invalidateQueries({ queryKey: ["conversation", conversationId] });
      queryClient.invalidateQueries({ queryKey: ["conversations"] });
    },
    onError: (error: any) => {
      const detail =
        error?.response?.data?.detail ||
        (error?.message === "Network Error" ? "Network error" : null);
      setSourcesUpdateError(detail || "Unable to reprocess video. Please try again.");
    },
  });

  const sendMessageMutation = useMutation({
    mutationFn: async (text: string) => {
      if (!conversationId) return;
      const response = await conversationsApi.sendMessage(
        conversationId,
        text,
        false,
        selectedModelId || undefined,
        selectedMode,
      );

      // Optimistically append the assistant message to the conversation cache
      queryClient.setQueryData<ConversationWithMessages | undefined>(
        ["conversation", conversationId],
        (prev) =>
          prev
            ? {
                ...prev,
                messages: [
                  ...prev.messages,
                  {
                    id: response.message_id,
                    conversation_id: response.conversation_id,
                    role: "assistant",
                    content: response.content,
                    token_count: response.token_count,
                    chunks_retrieved_count: response.chunk_references?.length ?? undefined,
                    response_time_seconds: response.response_time_seconds,
                    created_at: new Date().toISOString(),
                    // Attach chunk_references so the sources panel can render.
                    // This extends the Message type locally without changing shared types.
                    chunk_references: response.chunk_references,
                  } as Message & { chunk_references?: ChunkReference[] },
                ],
              }
            : prev,
      );

      return response;
    },
    onMutate: () => {
      setSendError(null);
    },
    onSuccess: () => {
      setMessageText("");
      setSendError(null);
      queryClient.invalidateQueries({ queryKey: ["conversation", conversationId] });
    },
    onError: (error: any) => {
      const detail =
        error?.response?.data?.detail ||
        (error?.message === "Network Error" ? "Network error" : null);
      setSendError(detail || "Unable to send message. Check your sources and try again.");
    },
  });

  // Memoized citation click handler (no dependencies, safe to cache)
  const handleCitationClick = useCallback((messageId: string, rank?: number) => {
    if (!rank) return;
    const targetId = `source-${messageId}-${rank}`;
    const el = document.getElementById(targetId);
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "center" });
      setHighlightedSourceId(targetId);
      window.setTimeout(() => setHighlightedSourceId(null), 1500);
    }
  }, []);

  const handleBack = () => {
    router.push("/conversations");
  };

  if (!isAuthenticated) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <div className="flex flex-col items-center justify-center gap-3 text-center">
          <p className="text-sm font-medium text-muted-foreground">Sign in to view this conversation.</p>
          <div className="flex flex-col gap-2 sm:flex-row">
            <Button asChild>
              <Link href="/sign-up">Create account</Link>
            </Button>
            <Button asChild variant="outline">
              <Link href="/login">Sign in</Link>
            </Button>
          </div>
        </div>
      </div>
    );
  }

  if (!conversationId) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <div className="flex flex-col items-center justify-center gap-3 text-center">
          <p className="text-sm font-medium text-destructive">Conversation not found</p>
          <Button variant="outline" size="sm" onClick={handleBack}>
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to conversations
          </Button>
        </div>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <div className="flex items-center text-muted-foreground">
          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          Loading conversation...
        </div>
      </div>
    );
  }

  if (isError || !conversation) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <div className="flex flex-col items-center justify-center gap-3 text-center">
          <p className="text-sm font-medium text-destructive">Unable to load conversation</p>
          <p className="text-xs text-muted-foreground">
            Please check your connection or try again from the conversations page.
          </p>
          <Button variant="outline" size="sm" onClick={handleBack}>
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to conversations
          </Button>
        </div>
      </div>
    );
  }

  const selectedModel =
    MODEL_OPTIONS.find((option) => option.id === selectedModelId) ?? MODEL_OPTIONS[0];
  const selectedModeDetails =
    MODE_OPTIONS.find((option) => option.id === selectedMode) ?? MODE_OPTIONS[0];

  const sources = sourcesData?.sources ?? [];
  const selectedSourcesCount =
    sourcesData?.selected ?? sources.filter((source) => source.is_selected).length;
  const totalSourcesCount = sourcesData?.total ?? sources.length;
  const sourceCountLabel =
    totalSourcesCount || conversation?.selected_video_ids?.length || 0;

  const formatDuration = (seconds?: number | null) => {
    if (!seconds && seconds !== 0) return "";
    const totalSeconds = Math.floor(seconds || 0);
    const hours = Math.floor(totalSeconds / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    const secs = totalSeconds % 60;
    if (hours > 0) {
      return `${hours.toString().padStart(2, "0")}:${minutes
        .toString()
        .padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
    }
    return `${minutes.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
  };

  // Event handlers (regular functions - no useCallback needed after early returns)
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!messageText.trim() || isStreaming || !conversationId) {
      return;
    }
    if (selectedSourcesCount === 0) {
      setSendError("Select at least one source to ask a question.");
      return;
    }

    const text = messageText.trim();
    setMessageText(""); // Clear input immediately for responsiveness
    setSendError(null);

    // Use streaming for the message
    await sendStreamingMessage(text, selectedModelId || undefined, selectedMode);
  };

  const handleSelectAllSources = () => {
    if (!conversationId || sources.length === 0) return;
    const selectableSources = sources.filter((source) => source.selectable !== false);
    updateSourcesMutation.mutate({
      selected_video_ids: selectableSources.map((source) => source.video_id),
    });
    const excludedCount = sources.length - selectableSources.length;
    if (excludedCount > 0) {
      setSourcesUpdateError(
        `${excludedCount} source(s) can’t be selected yet (deleted or not finished processing).`,
      );
    }
  };

  const handleDeselectAllSources = () => {
    if (!conversationId) return;
    updateSourcesMutation.mutate({
      selected_video_ids: [],
    });
  };

  const toggleSourceSelection = (videoId: string) => {
    if (!conversationId || sources.length === 0) return;
    const targetSource = sources.find((s) => s.video_id === videoId);
    if (targetSource?.selectable === false) {
      setSourcesUpdateError(targetSource.selectable_reason || "This source can’t be selected yet.");
      return;
    }
    const currentlySelected = sources.filter((s) => s.is_selected).map((s) => s.video_id);
    const isCurrentlySelected = currentlySelected.includes(videoId);
    const nextSelected = isCurrentlySelected
      ? currentlySelected.filter((id) => id !== videoId)
      : Array.from(new Set([...currentlySelected, videoId]));

    updateSourcesMutation.mutate({
      selected_video_ids: nextSelected,
    });
  };

  const renderSourcesContent = () => (
    <div className="space-y-3">
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-sm font-medium">Sources</p>
          <p className="text-xs text-muted-foreground">
            Using {selectedSourcesCount} of {totalSourcesCount}
          </p>
          {sourcesUpdateError && (
            <p className="mt-1 text-xs text-destructive">{sourcesUpdateError}</p>
          )}
        </div>
        <div className="flex gap-2">
          <Button
            size="sm"
            variant="outline"
            className="text-xs"
            onClick={handleDeselectAllSources}
            disabled={updateSourcesMutation.isPending || sources.length === 0}
          >
            None
          </Button>
          <Button
            size="sm"
            variant="outline"
            className="text-xs"
            onClick={handleSelectAllSources}
            disabled={updateSourcesMutation.isPending || sources.length === 0}
          >
            All
          </Button>
        </div>
      </div>
      <div className="max-h-[65vh] space-y-2 overflow-y-auto pr-1">
        {sourcesLoading ? (
          <p className="text-xs text-muted-foreground">Loading sources…</p>
        ) : sources.length === 0 ? (
          <p className="text-xs text-muted-foreground">No sources attached yet.</p>
        ) : (
          sources.map((source) => (
            <label
              key={source.video_id}
              className="flex cursor-pointer items-start gap-2 rounded-md border bg-background px-2 py-2"
            >
              <Checkbox
                checked={source.is_selected}
                onCheckedChange={() => toggleSourceSelection(source.video_id)}
                disabled={
                  updateSourcesMutation.isPending ||
                  reprocessVideoMutation.isPending ||
                  source.selectable === false
                }
              />
              <div className="flex flex-1 flex-col gap-1">
                <div className="flex items-center gap-2">
                  <span className="line-clamp-2 text-sm font-medium">
                    {source.title || "Untitled video"}
                  </span>
                  {source.status && (
                    <Badge variant="outline" className="text-[10px] uppercase">
                      {source.status}
                    </Badge>
                  )}
                </div>
                <div className="flex flex-wrap items-center gap-2 text-[11px] text-muted-foreground">
                  {source.duration_seconds ? (
                    <span>{formatDuration(source.duration_seconds)}</span>
                  ) : null}
                  {source.added_via && <span>via {source.added_via}</span>}
                </div>
                {source.selectable === false && (
                  <div className="flex items-center justify-between gap-2 text-[11px] text-destructive">
                    <span className="line-clamp-1">{source.selectable_reason}</span>
                    {!source.is_deleted && (
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        className="h-6 px-2 text-[11px]"
                        onClick={(e) => {
                          e.preventDefault();
                          e.stopPropagation();
                          reprocessVideoMutation.mutate(source.video_id);
                        }}
                        disabled={reprocessVideoMutation.isPending}
                      >
                        Reprocess
                      </Button>
                    )}
                  </div>
                )}
              </div>
            </label>
          ))
        )}
      </div>
    </div>
  );


  return (
    <div className="flex h-screen overflow-hidden bg-background">
      {/* Sidebar - ChatGPT style */}
      <div
        className={cn(
          "fixed inset-y-0 left-0 z-50 w-64 transform border-r bg-background transition-transform duration-200 ease-in-out lg:relative lg:translate-x-0",
          sidebarOpen ? "translate-x-0" : "-translate-x-full"
        )}
      >
        <div className="flex h-full flex-col">
          {/* Sidebar header */}
          <div className="flex h-14 items-center justify-between border-b px-3">
            <Link href="/conversations" className="flex items-center gap-2">
              <div className="flex h-7 w-7 items-center justify-center rounded-md bg-primary text-primary-foreground">
                <span className="text-xs font-bold">RT</span>
              </div>
              <span className="text-sm font-semibold">RAG Transcript</span>
            </Link>
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8 lg:hidden"
              onClick={() => setSidebarOpen(false)}
            >
              <X className="h-4 w-4" />
            </Button>
          </div>

          {/* New chat button */}
          <div className="p-3">
            <Link href="/conversations">
              <Button variant="outline" className="w-full justify-start gap-2" size="sm">
                <Plus className="h-4 w-4" />
                New chat
              </Button>
            </Link>
          </div>

          {/* Recent conversations */}
          <div className="flex-1 overflow-y-auto px-2">
            <div className="space-y-1">
              {conversations.map((conv: Conversation) => (
                <div key={conv.id} className="space-y-1">
                  <Link href={`/conversations/${conv.id}`}>
                    <Button
                      variant="ghost"
                      className={cn(
                        "w-full justify-start gap-2 text-xs",
                        conv.id === conversationId && "bg-muted"
                      )}
                      size="sm"
                    >
                      <MessageCircle className="h-3.5 w-3.5 flex-shrink-0" />
                      <span className="truncate">{conv.title || "Untitled"}</span>
                    </Button>
                  </Link>

                  {conv.id === conversationId && (
                    <div className="ml-4 space-y-1 border-l pl-3">
                      {sourcesLoading ? (
                        <p className="text-[11px] text-muted-foreground">Loading sources…</p>
                      ) : sources.length === 0 ? (
                        <p className="text-[11px] text-muted-foreground">
                          No sources attached.
                        </p>
                      ) : (
                        sources.map((source) => (
                          <label
                            key={source.video_id}
                            className="flex cursor-pointer items-center gap-2 text-[11px] text-foreground"
                            onClick={(e) => e.stopPropagation()}
                            title={source.selectable === false ? source.selectable_reason ?? undefined : undefined}
                          >
                            <Checkbox
                              checked={source.is_selected}
                              onCheckedChange={() => toggleSourceSelection(source.video_id)}
                              className="h-3.5 w-3.5"
                              disabled={
                                updateSourcesMutation.isPending ||
                                reprocessVideoMutation.isPending ||
                                source.selectable === false
                              }
                            />
                            <span className="line-clamp-1 flex-1">
                              {source.title || "Untitled video"}
                            </span>
                          </label>
                        ))
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Navigation - MainLayout style */}
          <nav className="space-y-1 px-2 py-3 border-t">
            <Link
              href="/videos"
              className={cn(
                "group flex items-center justify-between rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                "text-muted-foreground hover:text-foreground"
              )}
            >
              <span className="flex items-center gap-2">
                <Video className="h-4 w-4" />
                Videos
              </span>
            </Link>
            <Link
              href="/collections"
              className={cn(
                "group flex items-center justify-between rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                "text-muted-foreground hover:text-foreground"
              )}
            >
              <span className="flex items-center gap-2">
                <Folder className="h-4 w-4" />
                Collections
              </span>
            </Link>
            <Link
              href="/conversations"
              className={cn(
                "group flex items-center justify-between rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                "bg-primary/10 text-foreground"
              )}
            >
              <span className="flex items-center gap-2">
                <MessageSquare className="h-4 w-4" />
                Conversations
              </span>
            </Link>
            <Link
              href="/account"
              className={cn(
                "group flex items-center justify-between rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                "text-muted-foreground hover:text-foreground"
              )}
            >
              <span className="flex items-center gap-2">
                <User className="h-4 w-4" />
                Account
              </span>
            </Link>
            {hasAdminAccess && (
              <Link
                href="/admin"
                className={cn(
                  "group flex items-center justify-between rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                  "text-muted-foreground hover:text-foreground",
                  "border-t mt-2 pt-4"
                )}
              >
                <span className="flex items-center gap-2">
                  <Shield className="h-4 w-4" />
                  Admin
                </span>
              </Link>
            )}
          </nav>

          {/* Quota indicator */}
          {quota && (
            <div className="border-t px-4 py-3">
              <p className="text-xs font-semibold text-muted-foreground mb-2">QUOTA</p>
              <div className="space-y-1.5">
                <QuotaDisplay
                  used={quota.videos_used}
                  limit={quota.videos_limit}
                  label="videos"
                  variant="compact"
                />
                <QuotaDisplay
                  used={quota.messages_used}
                  limit={quota.messages_limit}
                  label="messages/mo"
                  variant="compact"
                />
              </div>
            </div>
          )}

          {/* User profile section */}
          {user && (
            <div className="border-t px-4 py-4 text-sm text-muted-foreground">
              <p className="font-medium text-foreground">{displayName}</p>
              {email && <p>{email}</p>}
              <Button
                variant="ghost"
                size="sm"
                className="mt-3 w-full justify-start gap-2"
                onClick={handleLogout}
              >
                <LogOut className="h-4 w-4" />
                Logout
              </Button>
            </div>
          )}
        </div>
      </div>

      {/* Overlay for mobile */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Main content - Three column layout */}
      <div className="flex h-full flex-1 min-h-0">
        {/* Chat area column */}
        <div className="flex flex-1 flex-col min-w-0 min-h-0">
          {/* Top navigation bar */}
          <header className="sticky top-0 z-30 border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
            <div className="flex h-16 items-center px-4">
              <div className="flex flex-1 flex-col justify-center gap-0.5">
                {/* Primary: Title with mobile menu */}
                <div className="flex items-center gap-3">
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-9 w-9 lg:hidden"
                    onClick={() => setSidebarOpen(!sidebarOpen)}
                  >
                    <Menu className="h-5 w-5" />
                  </Button>
                  <Separator orientation="vertical" className="h-6 lg:hidden" />
                  <h1 className="text-sm font-medium truncate">
                    {conversation.title || "New conversation"}
                  </h1>
                </div>

                {/* Secondary: Metadata */}
                <div className="flex items-center gap-2 text-xs text-muted-foreground ml-10 lg:ml-0">
                  <span>
                    {selectedSourcesCount} of {totalSourcesCount} video
                    {totalSourcesCount !== 1 ? "s" : ""}
                  </span>
                  <span>•</span>
                  <span>
                    {conversation.message_count || messages.length} message
                    {(conversation.message_count || messages.length) !== 1 ? "s" : ""}
                  </span>
                  {conversation.last_message_at && (
                    <>
                      <span>•</span>
                      <span>
                        Active {formatDistanceToNow(new Date(conversation.last_message_at), { addSuffix: true })}
                      </span>
                    </>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-2">
                {/* Insights dialog */}
                <Dialog
                  open={insightsDialogOpen}
                  onOpenChange={(open) => {
                    setInsightsDialogOpen(open);
                    if (!open) setInsightsDialogMaximized(false);
                  }}
                >
                  <DialogTrigger asChild>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-9 w-9"
                      disabled={selectedSourcesCount === 0}
                      title={
                        selectedSourcesCount === 0
                          ? "Select at least one source to generate insights"
                          : "Generate a topic map from selected video sources"
                      }
                    >
                      <Network className="h-4 w-4" />
                    </Button>
                  </DialogTrigger>
                  <DialogContent
                    className={cn(
                      "p-0 flex flex-col gap-0",
                      insightsDialogMaximized
                        ? "max-w-[calc(100vw-1.5rem)] h-[calc(100vh-1.5rem)]"
                        : "max-w-6xl h-[85vh]"
                    )}
                  >
                    <DialogHeader className="p-6 pb-4">
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <DialogTitle>Conversation Insights: Topic Map</DialogTitle>
                          {insightsData?.metadata ? (
                            <p className="mt-1 text-xs text-muted-foreground">
                              {insightsData.metadata.cached ? "Cached" : "Generated"} •{" "}
                              {insightsData.metadata.topics_count} topics
                            </p>
                          ) : null}
                        </div>
                        <div className="flex items-center gap-2">
                          <Button
                            variant="outline"
                            size="sm"
                            className="gap-2"
                            onClick={() => setInsightsDialogMaximized((prev) => !prev)}
                            title={insightsDialogMaximized ? "Restore window" : "Enlarge window"}
                          >
                            {insightsDialogMaximized ? (
                              <Minimize2 className="h-4 w-4" />
                            ) : (
                              <Maximize2 className="h-4 w-4" />
                            )}
                            {insightsDialogMaximized ? "Restore" : "Enlarge"}
                          </Button>

                          <Button
                            variant="outline"
                            size="sm"
                            className="gap-2"
                            onClick={() => regenerateInsightsMutation.mutate()}
                            disabled={
                              regenerateInsightsMutation.isPending ||
                              insightsLoading ||
                              !conversationId
                            }
                          >
                            {regenerateInsightsMutation.isPending ? (
                              <Loader2 className="h-4 w-4 animate-spin" />
                            ) : (
                              <RotateCcw className="h-4 w-4" />
                            )}
                            Regenerate
                          </Button>
                        </div>
                      </div>
                    </DialogHeader>

                    <div className="flex-1 min-h-0 px-6 pb-6">
                      {insightsLoading || regenerateInsightsMutation.isPending ? (
                        <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
                          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                          Generating insights...
                        </div>
                      ) : insightsError ? (
                        <div className="flex h-full items-center justify-center text-sm text-destructive">
                          Failed to load insights.
                        </div>
                      ) : insightsData ? (
                        <ConversationInsightMap
                          conversationId={conversationId as string}
                          graphData={insightsData.graph}
                        />
                      ) : (
                        <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
                          No insights available.
                        </div>
                      )}
                    </div>
                  </DialogContent>
                </Dialog>

                <ThemeToggle />

                {/* Context panel toggle - desktop */}
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-9 w-9 hidden lg:flex"
                  onClick={() => setContextPanelOpen(!contextPanelOpen)}
                  title={contextPanelOpen ? "Hide settings panel" : "Show settings panel"}
                >
                  {contextPanelOpen ? (
                    <PanelRightClose className="h-4 w-4" />
                  ) : (
                    <PanelRightOpen className="h-4 w-4" />
                  )}
                </Button>

                {/* Sources panel toggle - mobile (opens sheet) */}
                <Sheet open={sourcesSheetOpen} onOpenChange={setSourcesSheetOpen}>
                  <SheetTrigger asChild>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-9 w-9 lg:hidden"
                      title="Open sources"
                    >
                      <Settings className="h-4 w-4" />
                    </Button>
                  </SheetTrigger>
                  <SheetContent side="right" className="w-full max-w-sm overflow-y-auto">
                    <div className="mt-4 space-y-6">
                      {/* Sources section */}
                      <div className="space-y-3">
                        <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                          Sources
                        </h3>
                        {renderSourcesContent()}
                      </div>
                    </div>
                  </SheetContent>
                </Sheet>
              </div>
            </div>
          </header>

          {/* Messages area - clean, focused */}
          <div ref={scrollContainerRef} className="flex-1 overflow-y-auto">
            <div className="mx-auto max-w-3xl px-4 py-6">
              {selectedSourcesCount === 0 && (
                <div className="mb-4 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-destructive">
                  No sources selected. Enable at least one source to ask questions.
                </div>
              )}

              {messages.length === 0 ? (
                <div className="flex h-[60vh] flex-col items-center justify-center gap-3 text-center">
                  <div className="flex h-12 w-12 items-center justify-center rounded-full bg-primary/10">
                    <MessageCircle className="h-6 w-6 text-primary" />
                  </div>
                  <div className="space-y-1">
                    <p className="text-sm font-medium">Start a conversation</p>
                    <p className="text-xs text-muted-foreground">
                      Ask questions about your {sourceCountLabel} source
                      {sourceCountLabel !== 1 ? "s" : ""}
                    </p>
                  </div>
                </div>
              ) : (
                <div className="space-y-8">
                  {messages.map((message) => (
                    <MessageItem
                      key={message.id}
                      message={message as Message & { chunk_references?: ChunkReference[] }}
                      highlightedSourceId={highlightedSourceId}
                      onCitationClick={handleCitationClick}
                    />
                  ))}
                  {/* Streaming message - shown while AI is responding */}
                  {isStreaming && (
                    <StreamingMessage
                      content={streamingContent}
                      isStreaming={isStreaming}
                      elapsedTime={elapsedTime}
                    />
                  )}
                  {/* Error display for streaming errors */}
                  {streamingError && !isStreaming && (
                    <div className="flex w-full justify-start">
                      <div className="w-full max-w-[90%] rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
                        {streamingError}
                      </div>
                    </div>
                  )}
                  <div ref={messagesEndRef} />
                </div>
              )}
            </div>
          </div>

          {/* Input area with settings */}
          <div className="sticky bottom-0 border-t bg-background/95 backdrop-blur">
            <div className="mx-auto max-w-3xl px-4 py-4">
              {/* Settings row above input */}
              <div className="mb-3 flex flex-wrap items-center gap-3">
                <div className="flex items-center gap-1">
                  <label className="text-xs text-muted-foreground whitespace-nowrap">Model:</label>
                  <select
                    value={selectedModelId}
                    onChange={(e) => setSelectedModelId(e.target.value)}
                    className="rounded-md border border-border bg-background px-2 py-1 text-xs text-foreground focus-visible:border-primary focus-visible:ring-1 focus-visible:ring-primary/40"
                  >
                    {MODEL_OPTIONS.map((option) => (
                      <option key={option.id} value={option.id}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                  <TooltipProvider>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <Info className="h-3.5 w-3.5 text-muted-foreground cursor-help ml-1" />
                      </TooltipTrigger>
                      <TooltipContent side="top" className="max-w-xs">
                        <p className="text-sm">{selectedModel.tooltip}</p>
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                </div>
                <div className="flex items-center gap-2">
                  <label className="text-xs text-muted-foreground whitespace-nowrap">Mode:</label>
                  <select
                    value={selectedMode}
                    onChange={(e) => setSelectedMode(e.target.value as ModeId)}
                    className="rounded-md border border-border bg-background px-2 py-1 text-xs text-foreground focus-visible:border-primary focus-visible:ring-1 focus-visible:ring-primary/40"
                  >
                    {MODE_OPTIONS.map((option) => (
                      <option key={option.id} value={option.id}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <form onSubmit={handleSubmit}>
                <div className="flex items-center gap-3">
                  <Input
                    id="message"
                    placeholder="Ask InsightGuide about the transcript..."
                    value={messageText}
                    onChange={(e) => setMessageText(e.target.value)}
                    disabled={isStreaming}
                    className="flex-1 rounded-xl border border-border bg-muted/50 px-4 py-3 text-sm shadow-none focus:border-primary focus:ring-0"
                    autoComplete="off"
                  />
                  {isStreaming ? (
                    /* Stop button during streaming */
                    <Button
                      type="button"
                      size="icon"
                      variant="destructive"
                      className="h-10 w-10 rounded-xl"
                      onClick={cancelStream}
                      title="Stop generating"
                    >
                      <Square className="h-4 w-4" />
                    </Button>
                  ) : (
                    /* Send button when not streaming */
                    <Button
                      type="submit"
                      size="icon"
                      className="h-10 w-10 rounded-xl bg-primary text-primary-foreground hover:bg-primary/90"
                      disabled={!messageText.trim() || selectedSourcesCount === 0}
                    >
                      <svg
                        xmlns="http://www.w3.org/2000/svg"
                        viewBox="0 0 24 24"
                        fill="currentColor"
                        className="h-4 w-4"
                      >
                        <path d="M3.478 2.405a.75.75 0 00-.926.94l2.432 7.905H13.5a.75.75 0 010 1.5H4.984l-2.432 7.905a.75.75 0 00.926.94 60.519 60.519 0 0018.445-8.986.75.75 0 000-1.218A60.517 60.517 0 003.478 2.405z" />
                      </svg>
                    </Button>
                  )}
                </div>

                {/* Inline sources summary when context panel is collapsed */}
                {!contextPanelOpen && (
                  <button
                    type="button"
                    onClick={() => setContextPanelOpen(true)}
                    className="mt-2 flex items-center gap-2 text-xs text-muted-foreground hover:text-foreground transition-colors"
                  >
                    <Settings className="h-3 w-3" />
                    <span>
                      {selectedSourcesCount} source{selectedSourcesCount !== 1 ? "s" : ""} selected
                    </span>
                  </button>
                )}

                {sendError && (
                  <p className="mt-2 text-[11px] text-destructive">{sendError}</p>
                )}
              </form>
            </div>
          </div>
        </div>

        {/* Context panel - desktop only, collapsible */}
        <aside
          className={cn(
            "hidden lg:flex flex-col w-72 border-l bg-background transition-all duration-200 overflow-hidden",
            contextPanelOpen ? "translate-x-0" : "translate-x-full w-0 border-l-0"
          )}
        >
          {/* Panel header */}
          <div className="flex h-14 items-center justify-between border-b px-4">
            <span className="text-sm font-medium">Context</span>
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8"
              onClick={() => setContextPanelOpen(false)}
            >
              <X className="h-4 w-4" />
            </Button>
          </div>

          {/* Panel content - scrollable */}
          <div className="flex-1 overflow-y-auto">
            {/* Sources section */}
            <div className="p-4">
              <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-3">
                Sources
              </h3>
              {renderSourcesContent()}
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}
