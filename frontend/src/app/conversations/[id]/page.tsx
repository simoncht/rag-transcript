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
import { useAuth, createParallelQueryFn } from "@/lib/auth";
import { conversationsApi } from "@/lib/api/conversations";
import { insightsApi } from "@/lib/api/insights";
import { videosApi } from "@/lib/api/videos";
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
import { cn, formatMessageTime } from "@/lib/utils";
import { ConversationInsightMap } from "@/components/insights/ConversationInsightMap";
import {
  ArrowLeft,
  Loader2,
  MessageCircle,
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
  // Ollama Cloud Models (Free - runs on Ollama Cloud infrastructure)
  {
    id: "qwen3-vl:235b-instruct-cloud",
    label: "Qwen3 VL 235B",
    description: "Free - Vision & deep reasoning (Ollama Cloud)",
  },
  {
    id: "gpt-oss:120b-cloud",
    label: "GPT-OSS 120B",
    description: "Free - Broad context understanding (Ollama Cloud)",
  },
  {
    id: "qwen3-coder:480b-cloud",
    label: "Qwen3 Coder 480B",
    description: "Free - Code-focused large model (Ollama Cloud)",
  },
  // Anthropic Models (Paid API)
  {
    id: "claude-3-5-sonnet-20241022",
    label: "Claude 3.5 Sonnet",
    description: "Paid - Best balance of speed and intelligence",
  },
  {
    id: "claude-3-opus-20240229",
    label: "Claude 3 Opus",
    description: "Paid - Most capable for complex tasks",
  },
  {
    id: "claude-3-haiku-20240307",
    label: "Claude 3 Haiku",
    description: "Paid - Fastest for simple tasks",
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
  {
    id: "timeline",
    label: "Timeline",
    helper: "Sequence events chronologically",
  },
  {
    id: "extract_actions",
    label: "Extract Actions",
    helper: "List concrete decisions and owners",
  },
  {
    id: "quiz_me",
    label: "Quiz Me",
    helper: "Pose knowledge-check questions",
  },
];
type ModeId = (typeof MODE_OPTIONS)[number]["id"];

// Helper function: linkify source mentions in markdown content
// Memoized per message to avoid regex processing on every render
const linkifySourceMentions = (
  content: string,
  messageId: string,
  chunkRefs?: ChunkReference[],
) => {
  return content.replace(/Source (\d+)/g, (_match, srcNumber) => {
    const rank = Number(srcNumber?.trim());
    if (!chunkRefs || chunkRefs.length === 0 || Number.isNaN(rank)) {
      return `Source ${srcNumber} (citation unavailable)`;
    }
    const match = chunkRefs?.find((chunk) => (chunk.rank ?? 0) === rank);
    const label = match?.video_title ? `Source ${rank}: ${match.video_title}` : `Source ${rank}`;
    return `[${label}](#source-${messageId}-${rank})`;
  });
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
      // Simply trigger the citation click - all sources are now shown equally
      onCitationClick(message.id, rank);
    },
    [message.id, onCitationClick]
  );

  // Performance: Memoize markdown components - combine static with dynamic anchor
  const markdownComponents = useMemo(() => ({
    ...MARKDOWN_STATIC_COMPONENTS,
    a: ({ href, children, ...props }: any) => {
      const isCitation = href?.startsWith("#source-");
      const rankMatch = href?.match(/#source-[^-]+-(\d+)/);
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

        {/* Sources section - grouped by video for multi-video conversations */}
        {isAssistant && totalSources > 0 && (
          <div className="space-y-3 rounded-lg border border-border bg-muted/30 p-3">
            {/* Header with source count and video count */}
            <div className="flex flex-wrap items-center gap-2">
              <p className="text-xs font-medium">
                Sources ({totalSources}{totalVideos > 1 ? ` from ${totalVideos} videos` : ""})
              </p>
            </div>

            {/* Sources grouped by video */}
            <div className="space-y-4">
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
          </div>
        )}
      </div>
    </div>
  );
});

MessageItem.displayName = "MessageItem";

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
  const [sourcesSheetOpen, setSourcesSheetOpen] = useState(false);
  const [insightsDialogOpen, setInsightsDialogOpen] = useState(false);
  const [insightsDialogMaximized, setInsightsDialogMaximized] = useState(false);
  const [highlightedSourceId, setHighlightedSourceId] = useState<string | null>(null);
  const [sendError, setSendError] = useState<string | null>(null);
  const [sourcesUpdateError, setSourcesUpdateError] = useState<string | null>(null);
  const [selectedModelId, setSelectedModelId] = useState<string>(MODEL_OPTIONS[0]?.id);
  const [selectedMode, setSelectedMode] = useState<ModeId>(MODE_OPTIONS[0].id);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const prevMessageCountRef = useRef<number>(0);
  const handleLogout = () => {
    authProvider.signOut("/sign-in");
  };

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
  useEffect(() => {
    const nextNonSystemLength = messages.filter((m) => m.role !== "system").length;
    if (isAutoScrollEnabled && nextNonSystemLength > prevMessageCountRef.current) {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
    }
    prevMessageCountRef.current = nextNonSystemLength;
  }, [messages, isAutoScrollEnabled]);

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
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!messageText.trim() || sendMessageMutation.isPending || !conversationId) {
      return;
    }
    if (selectedSourcesCount === 0) {
      setSendError("Select at least one source to ask a question.");
      return;
    }
    setSendError(null);
    sendMessageMutation.mutate(messageText.trim());
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
    <div className="flex min-h-screen bg-background">
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

          {/* Navigation */}
          <div className="border-t p-2">
            <Link href="/videos">
              <Button variant="ghost" className="w-full justify-start gap-2" size="sm">
                <Video className="h-4 w-4" />
                Videos
              </Button>
            </Link>
            <Link href="/collections">
              <Button variant="ghost" className="w-full justify-start gap-2" size="sm">
                <Folder className="h-4 w-4" />
                Collections
              </Button>
            </Link>
          </div>
        </div>
      </div>

      {/* Overlay for mobile */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Main content */}
      <div className="flex min-h-screen flex-1 flex-col">
        {/* Top navigation bar - ChatGPT style */}
        <header className="sticky top-0 z-30 border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
          <div className="flex h-14 items-center px-4">
            <div className="flex flex-1 items-center gap-3">
              <Button
                variant="ghost"
                size="icon"
                className="h-9 w-9"
                onClick={() => setSidebarOpen(!sidebarOpen)}
              >
                <Menu className="h-5 w-5" />
              </Button>
              <Separator orientation="vertical" className="h-6" />
              <h1 className="text-sm font-medium truncate">
                {conversation.title || "New conversation"}
              </h1>
            </div>
            <div className="flex items-center gap-3">
              <Dialog
                open={insightsDialogOpen}
                onOpenChange={(open) => {
                  setInsightsDialogOpen(open);
                  if (!open) setInsightsDialogMaximized(false);
                }}
              >
                <DialogTrigger asChild>
                  <Button
                    variant="outline"
                    size="sm"
                    className="gap-2"
                    disabled={selectedSourcesCount === 0}
                    title={
                      selectedSourcesCount === 0
                        ? "Select at least one source to generate insights"
                        : "Generate a topic map from selected video sources"
                    }
                  >
                    <Network className="h-4 w-4" />
                    Insights
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
              {authState.isAuthenticated && authState.user && (
                <Button
                  variant="outline"
                  size="sm"
                  className="gap-2"
                  onClick={handleLogout}
                >
                  <LogOut className="h-4 w-4" />
                  Sign out
                </Button>
              )}
            </div>
          </div>
        </header>

        {/* Messages area - centered like ChatGPT */}
        <div className="flex-1 overflow-y-auto">
          <div className="mx-auto max-w-[1220px] px-5 py-8">
            <div className="mb-4 flex items-center justify-between gap-3">
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <span className="font-semibold text-foreground">
                  Using {selectedSourcesCount} of {totalSourcesCount} sources
                </span>
                {updateSourcesMutation.isPending && (
                  <Loader2 className="h-3.5 w-3.5 animate-spin text-muted-foreground" />
                )}
              </div>
              <Sheet open={sourcesSheetOpen} onOpenChange={setSourcesSheetOpen}>
                <SheetTrigger asChild>
                  <Button variant="outline" size="sm" className="lg:hidden">
                    Sources
                  </Button>
                </SheetTrigger>
                <SheetContent side="right" className="w-full max-w-sm">
                  <div className="mt-4 space-y-4">{renderSourcesContent()}</div>
                </SheetContent>
              </Sheet>
            </div>

            {selectedSourcesCount === 0 && (
              <div className="mb-4 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-destructive">
                No sources selected. Enable at least one source to ask questions.
              </div>
            )}

            <div className="flex flex-col gap-6 lg:flex-row">
              <div className="flex-1 min-w-0">
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
                    <div ref={messagesEndRef} />
                  </div>
                )}
              </div>

              <div className="hidden w-80 flex-shrink-0 lg:block">
                <div className="sticky top-20 rounded-lg border border-border bg-muted/20 p-3">
                  {renderSourcesContent()}
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Input area - fixed at bottom like ChatGPT */}
        <div className="sticky bottom-0 border-t bg-background/80 backdrop-blur">
          <div className="mx-auto w-full max-w-[1220px] px-5 py-4">
            <form onSubmit={handleSubmit}>
              <div className="rounded-2xl border border-border bg-muted/70 p-4 shadow-inner">
                <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                  <div className="flex-1">
                    <div className="flex flex-wrap items-center gap-3">
                      <span className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground/70">
                        Model
                      </span>
                      <div className="flex flex-wrap gap-2">
                        {MODEL_OPTIONS.map((option) => (
                          <button
                            key={option.id}
                            type="button"
                            onClick={() => setSelectedModelId(option.id)}
                            className={cn(
                              "rounded-full border px-3 py-1 text-[11px] transition-colors",
                              selectedModelId === option.id
                                ? "border-primary bg-primary/20 text-primary"
                                : "border-border bg-background hover:border-primary/90 hover:text-primary",
                            )}
                          >
                            {option.label}
                          </button>
                        ))}
                      </div>
                    </div>
                    {selectedModel && (
                      <p className="mt-1 text-[11px] text-muted-foreground">
                        {selectedModel.label}: {selectedModel.description}
                      </p>
                    )}
                  </div>

                  <div className="flex max-w-xs flex-1 flex-col gap-2">
                    <label
                      htmlFor="response-mode"
                      className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground/70"
                    >
                      Mode
                    </label>
                    <select
                      id="response-mode"
                      value={selectedMode}
                      onChange={(event) =>
                        setSelectedMode(event.target.value as ModeId)
                      }
                      className="rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground focus-visible:border-primary focus-visible:ring-2 focus-visible:ring-primary/40"
                    >
                      {MODE_OPTIONS.map((modeOption) => (
                        <option key={modeOption.id} value={modeOption.id}>
                          {modeOption.label}
                        </option>
                      ))}
                    </select>
                    {selectedModeDetails && (
                      <p className="text-[11px] text-muted-foreground">
                        {selectedModeDetails.helper}
                      </p>
                    )}
                    </div>
                  </div>

                  <div className="mb-2 flex items-center justify-between text-[11px] text-muted-foreground">
                    <span>
                      Using {selectedSourcesCount} of {totalSourcesCount} sources
                    </span>
                    {selectedSourcesCount === 0 && (
                      <span className="text-destructive">Select a source to send a message</span>
                    )}
                  </div>

                  <div className="flex items-end gap-3">
                  <Input
                    id="message"
                    placeholder="Ask InsightGuide about the transcript..."
                    value={messageText}
                    onChange={(e) => setMessageText(e.target.value)}
                    disabled={sendMessageMutation.isPending}
                    className="flex-1 rounded-2xl border border-border bg-background/50 px-4 py-3 text-sm shadow-none focus:border-primary focus:ring-0"
                    autoComplete="off"
                  />
                  <Button
                    type="submit"
                    size="icon"
                    className="rounded-2xl border border-border bg-primary text-primary-foreground hover:bg-primary/90"
                    disabled={
                      sendMessageMutation.isPending ||
                      !messageText.trim() ||
                      selectedSourcesCount === 0
                    }
                  >
                    {sendMessageMutation.isPending ? (
                      <Loader2 className="h-5 w-5 animate-spin" />
                    ) : (
                      <svg
                        xmlns="http://www.w3.org/2000/svg"
                        viewBox="0 0 24 24"
                        fill="currentColor"
                        className="h-4 w-4"
                      >
                        <path d="M3.478 2.405a.75.75 0 00-.926.94l2.432 7.905H13.5a.75.75 0 010 1.5H4.984l-2.432 7.905a.75.75 0 00.926.94 60.519 60.519 0 0018.445-8.986.75.75 0 000-1.218A60.517 60.517 0 003.478 2.405z" />
                      </svg>
                    )}
                  </Button>
                </div>
                {sendError && (
                  <p className="mt-2 text-[11px] text-destructive">{sendError}</p>
                )}
              </div>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}
