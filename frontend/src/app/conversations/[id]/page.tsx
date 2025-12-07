"use client";

import { useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { conversationsApi } from "@/lib/api/conversations";
import type { ConversationWithMessages, Message, ChunkReference } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import { Badge } from "@/components/ui/badge";
import {
  Sheet,
  SheetContent,
  SheetTrigger,
} from "@/components/ui/sheet";
import { cn } from "@/lib/utils";
import {
  ArrowLeft,
  Loader2,
  MessageCircle,
  Menu,
  Plus,
  Video,
  Folder,
  X,
} from "lucide-react";
import Link from "next/link";
import { ThemeToggle } from "@/components/layout/ThemeToggle";
import type { Conversation } from "@/lib/types";

const MODEL_OPTIONS = [
  {
    id: "qwen3-vl:235b-instruct-cloud",
    label: "Qwen3 VL 235B (Cloud)",
    description: "Vision context depth textured reasoning",
  },
  {
    id: "gpt-oss:120b-cloud",
    label: "GPT-OSS 120B (Cloud)",
    description: "Broad context nuance pattern spotting",
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

export default function ConversationDetailPage() {
  const params = useParams();
  const router = useRouter();
  const conversationId = Array.isArray(params?.id) ? params.id[0] : (params?.id as string | undefined);

  const queryClient = useQueryClient();
  const [messageText, setMessageText] = useState("");
  const [isAutoScrollEnabled, setIsAutoScrollEnabled] = useState(true);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [sourcesSheetOpen, setSourcesSheetOpen] = useState(false);
  const [highlightedSourceId, setHighlightedSourceId] = useState<string | null>(null);
  const [sendError, setSendError] = useState<string | null>(null);
  const [selectedModelId, setSelectedModelId] = useState<string>(MODEL_OPTIONS[0]?.id);
  const [selectedMode, setSelectedMode] = useState<ModeId>(MODE_OPTIONS[0].id);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  // Fetch recent conversations for sidebar
  const { data: conversationsData } = useQuery({
    queryKey: ["conversations"],
    queryFn: () => conversationsApi.list(),
    refetchInterval: 10000,
  });

  const conversations = conversationsData?.conversations ?? [];

  const {
    data: conversation,
    isLoading,
    isError,
  } = useQuery<ConversationWithMessages>({
    queryKey: ["conversation", conversationId],
    queryFn: () => conversationsApi.get(conversationId as string),
    enabled: !!conversationId,
    refetchInterval: 5000,
  });

  const { data: sourcesData, isLoading: sourcesLoading } = useQuery({
    queryKey: ["conversation", conversationId, "sources"],
    queryFn: () => conversationsApi.getSources(conversationId as string),
    enabled: !!conversationId,
    refetchInterval: 5000,
  });

  const updateSourcesMutation = useMutation({
    mutationFn: (payload: { selected_video_ids?: string[]; add_video_ids?: string[] }) =>
      conversationsApi.updateSources(conversationId as string, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["conversation", conversationId, "sources"] });
      queryClient.invalidateQueries({ queryKey: ["conversation", conversationId] });
      queryClient.invalidateQueries({ queryKey: ["conversations"] });
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

  useEffect(() => {
    if (isAutoScrollEnabled && messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: "smooth", block: "end" });
    }
  }, [conversation?.messages?.length, isAutoScrollEnabled]);

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

  const handleBack = () => {
    router.push("/conversations");
  };

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

  const messages = conversation.messages ?? [];
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

  const handleSelectAllSources = () => {
    if (!conversationId || sources.length === 0) return;
    updateSourcesMutation.mutate({
      selected_video_ids: sources.map((source) => source.video_id),
    });
  };

  const handleDeselectAllSources = () => {
    if (!conversationId) return;
    updateSourcesMutation.mutate({
      selected_video_ids: [],
    });
  };

  const toggleSourceSelection = (videoId: string) => {
    if (!conversationId || sources.length === 0) return;
    const currentlySelected = sources.filter((s) => s.is_selected).map((s) => s.video_id);
    const isCurrentlySelected = currentlySelected.includes(videoId);
    const nextSelected = isCurrentlySelected
      ? currentlySelected.filter((id) => id !== videoId)
      : [...new Set([...currentlySelected, videoId])];

    updateSourcesMutation.mutate({
      selected_video_ids: nextSelected,
    });
  };

  const linkifySourceMentions = (content: string, messageId: string) =>
    content.replace(/Source (\d+)/g, (_match, srcNumber) => {
      const rank = srcNumber.trim();
      return `[Source ${rank}](#source-${messageId}-${rank})`;
    });

  const handleCitationClick = (messageId: string, rank?: number) => {
    if (!rank) return;
    const targetId = `source-${messageId}-${rank}`;
    const el = document.getElementById(targetId);
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "center" });
      setHighlightedSourceId(targetId);
      window.setTimeout(() => setHighlightedSourceId(null), 1500);
    }
  };

  const renderSourcesContent = () => (
    <div className="space-y-3">
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-sm font-medium">Sources</p>
          <p className="text-xs text-muted-foreground">
            Using {selectedSourcesCount} of {totalSourcesCount}
          </p>
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
                disabled={updateSourcesMutation.isPending}
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
                          >
                            <Checkbox
                              checked={source.is_selected}
                              onCheckedChange={() => toggleSourceSelection(source.video_id)}
                              className="h-3.5 w-3.5"
                              disabled={updateSourcesMutation.isPending}
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
            <div className="flex items-center gap-2">
              <ThemeToggle />
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
                    {messages.map((message) => {
                      const isUser = message.role === "user";
                      const withChunks = message as Message & {
                        chunk_references?: ChunkReference[];
                      };
                      const chunkReferences = withChunks.chunk_references;
                      const markdownContent = isUser
                        ? message.content
                        : linkifySourceMentions(message.content, message.id);

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
                            {/* Message header with avatar */}
                            <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
                              <span>
                                {new Date(message.created_at).toLocaleTimeString([], {
                                  hour: "2-digit",
                                  minute: "2-digit",
                                })}
                              </span>
                            </div>

                            {isUser ? (
                              <div className="w-full">
                                <p className="w-full rounded-2xl bg-primary/10 px-5 py-3 text-base leading-relaxed text-foreground shadow-lg">
                                  {message.content}
                                </p>
                              </div>
                            ) : (
                              <div className="w-full rounded-2xl border border-border bg-muted/40 p-4 shadow-sm">
                                <ReactMarkdown
                                  className="prose prose-base leading-relaxed max-w-full break-words dark:prose-invert"
                                  remarkPlugins={[remarkGfm]}
                                  components={{
                                    h1: ({ node, ...props }) => (
                                      <h1 className="mt-6 mb-3 text-base font-semibold leading-tight" {...props} />
                                    ),
                                    h2: ({ node, ...props }) => (
                                      <h2 className="mt-6 mb-3 text-base font-semibold leading-tight" {...props} />
                                    ),
                                    h3: ({ node, ...props }) => (
                                      <h3 className="mt-6 mb-3 text-base font-semibold leading-tight" {...props} />
                                    ),
                                    p: ({ node, ...props }) => (
                                      <p className="my-4 text-base leading-relaxed" {...props} />
                                    ),
                                    ul: ({ node, ...props }) => (
                                      <ul className="my-4 list-disc space-y-2 pl-5 leading-relaxed text-base" {...props} />
                                    ),
                                    ol: ({ node, ...props }) => (
                                      <ol className="my-4 list-decimal space-y-2 pl-5 leading-relaxed text-base" {...props} />
                                    ),
                                    li: ({ node, ordered, ...props }) => (
                                      <li className="leading-relaxed text-base" {...props} />
                                    ),
                                    table: ({ node, ...props }) => (
                                      <div className="my-5 overflow-hidden rounded-lg border border-border">
                                        <table className="w-full table-auto border-collapse text-sm" {...props} />
                                      </div>
                                    ),
                                    thead: ({ node, ...props }) => (
                                      <thead className="bg-muted/70" {...props} />
                                    ),
                                    tbody: ({ node, ...props }) => (
                                      <tbody className="divide-y divide-border" {...props} />
                                    ),
                                    tr: ({ node, ...props }) => (
                                      <tr className="divide-x divide-border" {...props} />
                                    ),
                                    th: ({ node, ...props }) => (
                                      <th
                                        className="px-3 py-2 text-left font-semibold text-foreground align-top whitespace-pre-wrap"
                                        {...props}
                                      />
                                    ),
                                    td: ({ node, ...props }) => (
                                      <td
                                        className="px-3 py-2 align-top text-foreground whitespace-pre-wrap"
                                        {...props}
                                      />
                                    ),
                                    a: ({ href, children, ...props }) => {
                                      const rankMatch = href?.match(/#source-[^-]+-(\d+)/);
                                      const rankNumber = rankMatch?.[1]
                                        ? parseInt(rankMatch[1], 10)
                                        : undefined;
                                      return (
                                        <a
                                          {...props}
                                          href={href}
                                          className="text-primary underline-offset-2 hover:underline"
                                          onClick={(event) => {
                                            if (href?.startsWith("#source-")) {
                                              event.preventDefault();
                                              handleCitationClick(message.id, rankNumber);
                                            }
                                          }}
                                        >
                                          {children}
                                        </a>
                                      );
                                    },
                                    hr: () => null,
                                  }}
                                >
                                  {markdownContent}
                                </ReactMarkdown>
                              </div>
                            )}

                            {/* Metadata for assistant messages */}
                            {!isUser && (
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

                            {/* Sources section */}
                            {!isUser && chunkReferences && chunkReferences.length > 0 && (
                              <div className="space-y-2 rounded-lg border border-border bg-muted/30 p-3">
                                <p className="text-xs font-medium">Sources</p>
                                <div className="space-y-2">
                                  {chunkReferences.map((chunk, idx) => {
                                    const chunkRank = chunk.rank ?? idx + 1;
                                    const sourceAnchorId = `source-${message.id}-${chunkRank}`;
                                    return (
                                      <div
                                        key={chunk.chunk_id}
                                        id={sourceAnchorId}
                                        className={cn(
                                          "rounded-md border bg-background/60 px-3 py-2 text-xs transition-shadow",
                                          highlightedSourceId === sourceAnchorId &&
                                            "ring-2 ring-primary/60 bg-primary/5"
                                        )}
                                      >
                                        <div className="mb-1 flex flex-wrap items-center gap-2">
                                          <span className="font-medium">{chunk.video_title}</span>
                                          <span className="text-muted-foreground">
                                            {chunk.timestamp_display}
                                          </span>
                                          <Badge variant="outline" className="text-[10px] uppercase">
                                            Source {chunkRank}
                                          </Badge>
                                          <span className="ml-auto text-[10px] text-muted-foreground">
                                            {(chunk.relevance_score * 100).toFixed(0)}% match
                                          </span>
                                        </div>
                                        <p className="text-[11px] text-muted-foreground leading-relaxed">
                                          {chunk.text_snippet}
                                        </p>
                                      </div>
                                    );
                                  })}
                                </div>
                              </div>
                            )}
                          </div>
                        </div>
                      );
                    })}
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






