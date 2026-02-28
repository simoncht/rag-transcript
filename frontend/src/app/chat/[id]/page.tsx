"use client";

import { useEffect, useRef, useState, useMemo, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuth, useAuthState, createParallelQueryFn } from "@/lib/auth";
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
import { Input } from "@/components/ui/input";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import { FollowUpQuestions } from "@/components/conversations/FollowUpQuestions";
import {
  ArrowLeft,
  Loader2,
  MessageCircle,
  Info,
  Square,
} from "lucide-react";
import Link from "next/link";
import {
  MessageItem,
  StreamingMessage,
  ChatHeader,
  MODEL_OPTIONS,
  MODE_OPTIONS,
  SourcesPanelProvider,
  SourcesPanel,
} from "@/components/chat";
import type { ModeId } from "@/components/chat";

const EMPTY_MESSAGES: Message[] = [];

export default function ChatConversationPage() {
  const params = useParams();
  const router = useRouter();
  const conversationId = Array.isArray(params?.id) ? params.id[0] : (params?.id as string | undefined);
  const authProvider = useAuth();
  const authState = authProvider.getState();
  const isAuthenticated = authState.isAuthenticated;
  const queryClient = useQueryClient();

  const [messageText, setMessageText] = useState("");
  const [isAutoScrollEnabled, setIsAutoScrollEnabled] = useState(true);
  const [insightsDialogOpen, setInsightsDialogOpen] = useState(false);
  const [highlightedSourceId, setHighlightedSourceId] = useState<string | null>(null);
  const [sendError, setSendError] = useState<string | null>(null);
  const [sourcesUpdateError, setSourcesUpdateError] = useState<string | null>(null);
  const [selectedModelId, setSelectedModelId] = useState<string>("deepseek-chat");
  const [selectedMode, setSelectedMode] = useState<ModeId>(MODE_OPTIONS[0].id);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const scrollContainerRef = useRef<HTMLDivElement | null>(null);
  const prevMessageCountRef = useRef<number>(0);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const pendingMessageSentRef = useRef(false);

  // Streaming message hook
  const {
    isStreaming,
    content: streamingContent,
    error: streamingError,
    elapsedTime,
    followupQuestions,
    statusStage,
    statusMessage,
    sendMessage: sendStreamingMessage,
    cancelStream,
  } = useStreamingMessage(conversationId || "");

  // Fetch conversation data
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
    refetchInterval: false,
    staleTime: 2 * 60 * 1000,
    gcTime: 5 * 60 * 1000,
  });

  const messages = useMemo(() => conversation?.messages ?? EMPTY_MESSAGES, [conversation?.messages]);

  // Scroll helpers
  const scrollToBottom = useCallback((behavior: ScrollBehavior = "smooth") => {
    const container = scrollContainerRef.current;
    if (container) {
      container.scrollTo({ top: container.scrollHeight, behavior });
    }
  }, []);

  useEffect(() => {
    const nextNonSystemLength = messages.filter((m) => m.role !== "system").length;
    if (isAutoScrollEnabled && nextNonSystemLength > prevMessageCountRef.current) {
      scrollToBottom("smooth");
    }
    prevMessageCountRef.current = nextNonSystemLength;
  }, [messages, isAutoScrollEnabled, scrollToBottom]);

  useEffect(() => {
    if (isStreaming && isAutoScrollEnabled && streamingContent) {
      scrollToBottom("smooth");
    }
  }, [isStreaming, streamingContent, isAutoScrollEnabled, scrollToBottom]);

  // Fetch sources
  const { data: sourcesData, isLoading: sourcesLoading } = useQuery({
    queryKey: ["conversation", conversationId, "sources"],
    queryFn: createParallelQueryFn(authProvider, () =>
      conversationsApi.getSources(conversationId as string)
    ),
    enabled: isAuthenticated && !!conversationId,
    refetchInterval: false,
    staleTime: 5 * 60 * 1000,
    gcTime: 10 * 60 * 1000,
  });

  // Fetch insights
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
    staleTime: 300000,
  });

  const regenerateInsightsMutation = useMutation({
    mutationFn: async () => {
      if (!conversationId) throw new Error("Missing conversationId");
      return insightsApi.getInsights(conversationId as string, true);
    },
    onSuccess: (data) => {
      queryClient.setQueryData(["conversation-insights", conversationId], data);
    },
  });

  const updateSourcesMutation = useMutation({
    mutationFn: (payload: { selected_video_ids?: string[]; add_video_ids?: string[] }) =>
      conversationsApi.updateSources(conversationId as string, payload),
    onMutate: () => setSourcesUpdateError(null),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["conversation", conversationId, "sources"] });
      queryClient.invalidateQueries({ queryKey: ["conversation", conversationId] });
      queryClient.invalidateQueries({ queryKey: ["conversations"] });
    },
    onError: (error: any) => {
      const detail = error?.response?.data?.detail || (error?.message === "Network Error" ? "Network error" : null);
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
      const detail = error?.response?.data?.detail || (error?.message === "Network Error" ? "Network error" : null);
      setSourcesUpdateError(detail || "Unable to reprocess video. Please try again.");
    },
  });

  // Pick up pending message from sessionStorage (implicit creation flow)
  useEffect(() => {
    if (!conversationId || !conversation || isStreaming || pendingMessageSentRef.current) return;
    const key = `pending-message-${conversationId}`;
    const pending = sessionStorage.getItem(key);
    if (pending) {
      sessionStorage.removeItem(key);
      pendingMessageSentRef.current = true;
      sendStreamingMessage(pending, selectedModelId || undefined, selectedMode);
    }
  }, [conversationId, conversation, isStreaming, sendStreamingMessage, selectedModelId, selectedMode]);

  // Handlers
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

  const handleCopyMessage = useCallback((messageId: string, content: string) => {
    navigator.clipboard.writeText(content);
    setCopiedId(messageId);
    setTimeout(() => setCopiedId(null), 2000);
  }, []);

  const handleFollowUpClick = useCallback(async (question: string) => {
    setMessageText("");
    setSendError(null);
    await sendStreamingMessage(question, selectedModelId || undefined, selectedMode);
  }, [sendStreamingMessage, selectedModelId, selectedMode]);

  const handleBack = () => router.push("/chat");

  // Source handlers
  const sources = useMemo(() => sourcesData?.sources ?? [], [sourcesData?.sources]);
  const selectedSourcesCount = sourcesData?.selected ?? sources.filter((s) => s.is_selected).length;
  const totalSourcesCount = sourcesData?.total ?? sources.length;
  const sourceCountLabel = totalSourcesCount || conversation?.selected_video_ids?.length || 0;

  const handleSelectAllSources = useCallback(() => {
    if (!conversationId || sources.length === 0) return;
    const selectableSources = sources.filter((s) => s.selectable !== false);
    updateSourcesMutation.mutate({ selected_video_ids: selectableSources.map((s) => s.video_id) });
    const excludedCount = sources.length - selectableSources.length;
    if (excludedCount > 0) {
      setSourcesUpdateError(`${excludedCount} source(s) can't be selected yet.`);
    }
  }, [conversationId, sources, updateSourcesMutation]);

  const handleDeselectAllSources = useCallback(() => {
    if (!conversationId) return;
    updateSourcesMutation.mutate({ selected_video_ids: [] });
  }, [conversationId, updateSourcesMutation]);

  const toggleSourceSelection = useCallback((videoId: string) => {
    if (!conversationId || sources.length === 0) return;
    const targetSource = sources.find((s) => s.video_id === videoId);
    if (targetSource?.selectable === false) {
      setSourcesUpdateError(targetSource.selectable_reason || "This source can't be selected yet.");
      return;
    }
    const currentlySelected = sources.filter((s) => s.is_selected).map((s) => s.video_id);
    const isCurrentlySelected = currentlySelected.includes(videoId);
    const nextSelected = isCurrentlySelected
      ? currentlySelected.filter((id) => id !== videoId)
      : Array.from(new Set([...currentlySelected, videoId]));
    updateSourcesMutation.mutate({ selected_video_ids: nextSelected });
  }, [conversationId, sources, updateSourcesMutation]);

  const handleReprocessSource = useCallback((videoId: string) => {
    reprocessVideoMutation.mutate(videoId);
  }, [reprocessVideoMutation]);

  const handleConversationDeleted = () => {
    router.push("/chat");
  };

  // Loading / error states
  if (!conversationId) {
    return (
      <div className="flex h-full flex-1 items-center justify-center">
        <div className="flex flex-col items-center gap-3 text-center">
          <p className="text-sm font-medium text-destructive">Conversation not found</p>
          <Button variant="outline" size="sm" onClick={handleBack}>
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to chat
          </Button>
        </div>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="flex h-full flex-1 items-center justify-center">
        <div className="flex items-center text-muted-foreground">
          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          Loading conversation...
        </div>
      </div>
    );
  }

  if (isError || !conversation) {
    return (
      <div className="flex h-full flex-1 items-center justify-center">
        <div className="flex flex-col items-center gap-3 text-center">
          <p className="text-sm font-medium text-destructive">Unable to load conversation</p>
          <p className="text-xs text-muted-foreground">Please check your connection or try again.</p>
          <Button variant="outline" size="sm" onClick={handleBack}>
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to chat
          </Button>
        </div>
      </div>
    );
  }

  const selectedModel = MODEL_OPTIONS.find((o) => o.id === selectedModelId) ?? MODEL_OPTIONS[0];

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!messageText.trim() || isStreaming || !conversationId) return;
    if (selectedSourcesCount === 0) {
      setSendError("Select at least one source to ask a question.");
      return;
    }
    const text = messageText.trim();
    setMessageText("");
    setSendError(null);
    await sendStreamingMessage(text, selectedModelId || undefined, selectedMode);
  };

  return (
    <SourcesPanelProvider
      value={{
        mode: "conversation",
        libraryItems: [],
        processingItems: [],
        selectedIds: [],
        selectedCollectionId: "",
        onSelectionChange: () => {},
        onCollectionChange: () => {},
        conversationSources: sources,
        selectedSourcesCount,
        totalSourcesCount,
        onToggleSource: toggleSourceSelection,
        onSelectAll: handleSelectAllSources,
        onDeselectAll: handleDeselectAllSources,
        sourcesUpdatePending: updateSourcesMutation.isPending,
        sourcesUpdateError,
        onReprocessSource: handleReprocessSource,
        reprocessPending: reprocessVideoMutation.isPending,
        isLoading: sourcesLoading,
        collections: [],
      }}
    >
      <div className="flex flex-1 flex-col min-w-0 min-h-0">
        {/* Header */}
        <ChatHeader
          conversation={conversation}
          conversationId={conversationId}
          messages={messages}
          selectedSourcesCount={selectedSourcesCount}
          totalSourcesCount={totalSourcesCount}
          insightsData={insightsData}
          insightsLoading={insightsLoading || regenerateInsightsMutation.isPending}
          insightsError={!!insightsError}
          insightsDialogOpen={insightsDialogOpen}
          onInsightsDialogChange={setInsightsDialogOpen}
          onRegenerateInsights={() => regenerateInsightsMutation.mutate()}
          regenerateInsightsPending={regenerateInsightsMutation.isPending}
          sidebarOpen={sidebarOpen}
          onToggleSidebar={() => setSidebarOpen(!sidebarOpen)}
          onConversationDeleted={handleConversationDeleted}
          onNavigateBack={handleBack}
        />

        {/* Messages area */}
        <div ref={scrollContainerRef} className="flex-1 overflow-y-auto">
          <div className="mx-auto max-w-3xl px-4 py-6">
            {selectedSourcesCount === 0 && (
              <div className="mb-4 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-destructive">
                No sources selected. Enable at least one source to ask questions.
              </div>
            )}

            {messages.length === 0 ? (
              <div className="flex h-[60vh] flex-col items-center justify-center gap-4 text-center">
                <div className="flex h-12 w-12 items-center justify-center rounded-full bg-primary/10">
                  <MessageCircle className="h-6 w-6 text-primary" />
                </div>
                <div className="space-y-1">
                  <p className="text-sm font-medium">Start a conversation</p>
                  <p className="text-xs text-muted-foreground">
                    Ask questions about your {sourceCountLabel} source{sourceCountLabel !== 1 ? "s" : ""}
                  </p>
                </div>
                {selectedSourcesCount > 0 && (
                  <div className="flex flex-wrap gap-2 justify-center max-w-md">
                    {(selectedSourcesCount >= 2
                      ? [
                          "Compare perspectives across sources",
                          "What common themes emerge?",
                          "Summarize all sources briefly",
                          "What are the key differences?",
                        ]
                      : [
                          "Summarize the key points",
                          "What are the main arguments?",
                          "List actionable takeaways",
                          "What topics are covered?",
                        ]
                    ).map((question) => (
                      <Button
                        key={question}
                        variant="outline"
                        size="sm"
                        className="text-xs"
                        onClick={async () => {
                          setMessageText("");
                          setSendError(null);
                          await sendStreamingMessage(question, selectedModelId || undefined, selectedMode);
                        }}
                        disabled={isStreaming}
                      >
                        {question}
                      </Button>
                    ))}
                  </div>
                )}
              </div>
            ) : (
              <div className="space-y-8">
                {messages.map((message) => (
                  <MessageItem
                    key={message.id}
                    message={message as Message & { chunk_references?: ChunkReference[] }}
                    highlightedSourceId={highlightedSourceId}
                    copiedId={copiedId}
                    onCitationClick={handleCitationClick}
                    onCopy={handleCopyMessage}
                    onFollowUpClick={handleFollowUpClick}
                  />
                ))}
                {isStreaming && (
                  <StreamingMessage
                    content={streamingContent}
                    isStreaming={isStreaming}
                    elapsedTime={elapsedTime}
                    statusStage={statusStage}
                    statusMessage={statusMessage}
                  />
                )}
                {!isStreaming && followupQuestions.length > 0 && (
                  <div className="flex w-full justify-start">
                    <div className="w-full max-w-[90%]">
                      <FollowUpQuestions
                        questions={followupQuestions}
                        onQuestionClick={async (question) => {
                          setMessageText("");
                          setSendError(null);
                          await sendStreamingMessage(question, selectedModelId || undefined, selectedMode);
                        }}
                        disabled={isStreaming}
                      />
                    </div>
                  </div>
                )}
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

        {/* Input area */}
        <div className="sticky bottom-0 border-t bg-background/95 backdrop-blur">
          <div className="mx-auto max-w-3xl px-4 py-4">
            {/* Settings row */}
            <div className="mb-3 flex flex-wrap items-center gap-3">
              <div className="flex items-center gap-1">
                <label className="text-xs text-muted-foreground whitespace-nowrap">Model:</label>
                <select
                  value={selectedModelId}
                  onChange={(e) => setSelectedModelId(e.target.value)}
                  className="rounded-md border border-border bg-background px-2 py-1 text-xs text-foreground focus-visible:border-primary focus-visible:ring-1 focus-visible:ring-primary/40"
                >
                  {MODEL_OPTIONS.map((option) => (
                    <option key={option.id} value={option.id}>{option.label}</option>
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
                    <option key={option.id} value={option.id}>{option.label}</option>
                  ))}
                </select>
              </div>
            </div>

            <form onSubmit={handleSubmit}>
              <div className="flex items-center gap-3">
                <Input
                  id="message"
                  placeholder="Ask about the content..."
                  value={messageText}
                  onChange={(e) => setMessageText(e.target.value)}
                  disabled={isStreaming}
                  className="flex-1 rounded-xl border border-border bg-muted/50 px-4 py-3 text-sm shadow-none focus:border-primary focus:ring-0"
                  autoComplete="off"
                />
                {isStreaming ? (
                  <Button type="button" size="icon" variant="destructive" className="h-10 w-10 rounded-xl" onClick={cancelStream} title="Stop generating">
                    <Square className="h-4 w-4" />
                  </Button>
                ) : (
                  <Button
                    type="submit"
                    size="icon"
                    className="h-10 w-10 rounded-xl bg-primary text-primary-foreground hover:bg-primary/90"
                    disabled={!messageText.trim() || selectedSourcesCount === 0}
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="h-4 w-4">
                      <path d="M3.478 2.405a.75.75 0 00-.926.94l2.432 7.905H13.5a.75.75 0 010 1.5H4.984l-2.432 7.905a.75.75 0 00.926.94 60.519 60.519 0 0018.445-8.986.75.75 0 000-1.218A60.517 60.517 0 003.478 2.405z" />
                    </svg>
                  </Button>
                )}
              </div>
              {sendError && <p className="mt-2 text-[11px] text-destructive">{sendError}</p>}
            </form>
          </div>
        </div>
      </div>

      <SourcesPanel />
    </SourcesPanelProvider>
  );
}
