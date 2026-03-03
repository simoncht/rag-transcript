"use client";

import { Suspense, useState, useEffect, useMemo, useCallback } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuthState } from "@/lib/auth";
import { conversationsApi } from "@/lib/api/conversations";
import { videosApi } from "@/lib/api/videos";
import { contentApi } from "@/lib/api/content";
import { getCollections } from "@/lib/api/collections";
import { SourcesPanelProvider, SourcesPanel, SourcesPanelToggle } from "@/components/chat";
import type { LibraryContentItem } from "@/components/chat";
import { useToast } from "@/hooks/use-toast";
import { ToastAction } from "@/components/ui/toast";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Loader2, MessageCircle, Square } from "lucide-react";

const PROCESSING_STATUSES = new Set([
  "pending",
  "downloading",
  "transcribing",
  "chunking",
  "enriching",
  "indexing",
]);

export default function ChatPage() {
  return (
    <Suspense
      fallback={
        <div className="flex h-full flex-1 items-center justify-center">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      }
    >
      <ChatPageContent />
    </Suspense>
  );
}

function ChatPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const authState = useAuthState();
  const canFetch = authState.isAuthenticated;

  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [selectedCollectionId, setSelectedCollectionId] = useState("");
  const [messageText, setMessageText] = useState("");

  const sourceParam = searchParams.get("source");
  const collectionParam = searchParams.get("collection");

  // Fetch completed videos
  const { data: videosData, isLoading: videosLoading } = useQuery({
    queryKey: ["videos-completed"],
    queryFn: () => videosApi.list(0, 100, "completed"),
    enabled: canFetch,
    staleTime: 60 * 1000,
  });

  // Fetch completed documents
  const { data: documentsData, isLoading: documentsLoading } = useQuery({
    queryKey: ["content-completed"],
    queryFn: () => contentApi.list(0, 100, undefined, "completed"),
    enabled: canFetch,
    staleTime: 60 * 1000,
  });

  // Fetch collections
  const { data: collectionsData } = useQuery({
    queryKey: ["collections"],
    queryFn: () => getCollections(),
    enabled: canFetch,
    staleTime: 60 * 1000,
  });

  // Fetch recent items (all statuses) for processing display
  const { data: recentVideosData } = useQuery({
    queryKey: ["videos-recent-all"],
    queryFn: () => videosApi.list(0, 20),
    enabled: canFetch,
    refetchInterval: 10_000,
  });

  const { data: recentDocsData } = useQuery({
    queryKey: ["content-recent-all"],
    queryFn: () => contentApi.list(0, 20),
    enabled: canFetch,
    refetchInterval: 10_000,
  });

  const isLoading = videosLoading || documentsLoading;

  // Build library items
  const libraryItems = useMemo<LibraryContentItem[]>(() => {
    const items: LibraryContentItem[] = [];
    if (videosData?.videos) {
      for (const v of videosData.videos) {
        if (v.status === "completed") {
          items.push({
            id: v.id,
            title: v.title || "Untitled video",
            type: "video",
            status: v.status,
            duration_seconds: v.duration_seconds,
            channel_name: v.channel_name,
            thumbnail_url: v.thumbnail_url,
          });
        }
      }
    }
    if (documentsData?.items) {
      for (const d of documentsData.items) {
        if (d.status === "completed") {
          items.push({
            id: d.id,
            title: d.title || "Untitled document",
            type: "document",
            status: d.status,
            page_count: d.page_count,
          });
        }
      }
    }
    return items;
  }, [videosData, documentsData]);

  // Build processing items
  const processingItems = useMemo<LibraryContentItem[]>(() => {
    const items: LibraryContentItem[] = [];
    const completedIds = new Set(libraryItems.map((i) => i.id));
    if (recentVideosData?.videos) {
      for (const v of recentVideosData.videos) {
        if (PROCESSING_STATUSES.has(v.status) && !completedIds.has(v.id)) {
          items.push({ id: v.id, title: v.title || "Untitled video", type: "video", status: v.status });
        }
      }
    }
    if (recentDocsData?.items) {
      for (const d of recentDocsData.items) {
        if (PROCESSING_STATUSES.has(d.status) && !completedIds.has(d.id)) {
          items.push({ id: d.id, title: d.title || "Untitled document", type: "document", status: d.status });
        }
      }
    }
    return items;
  }, [recentVideosData, recentDocsData, libraryItems]);

  const collections = collectionsData?.collections ?? [];

  // Create conversation mutation
  const createMutation = useMutation({
    mutationFn: ({
      title,
      options,
    }: {
      title: string;
      options: { selectedVideoIds?: string[]; collectionId?: string };
    }) => conversationsApi.create(title, options),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["conversations"] });
    },
  });

  // Auto-resume or create when ?source=<id> is present
  const [sourceHandled, setSourceHandled] = useState(false);
  useEffect(() => {
    if (sourceParam && canFetch && !sourceHandled && !createMutation.isPending) {
      setSourceHandled(true);
      (async () => {
        try {
          const existing = await conversationsApi.findBySource({ videoId: sourceParam });
          if (existing.total > 0) {
            router.push(`/chat/${existing.conversations[0].id}`);
            toast({
              title: "Resumed conversation",
              description: existing.conversations[0].title || "Previous conversation",
              action: (
                <ToastAction
                  altText="Start new conversation"
                  onClick={() => {
                    createMutation.mutate(
                      { title: "", options: { selectedVideoIds: [sourceParam] } },
                      { onSuccess: (data) => router.push(`/chat/${data.id}`) }
                    );
                  }}
                >
                  New chat
                </ToastAction>
              ),
            });
            return;
          }
        } catch {
          // Fall through to create
        }
        createMutation.mutate(
          { title: "", options: { selectedVideoIds: [sourceParam] } },
          { onSuccess: (data) => router.push(`/chat/${data.id}`) }
        );
      })();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sourceParam, canFetch, sourceHandled]);

  // Auto-resume or create when ?collection=<id> is present
  const [collectionHandled, setCollectionHandled] = useState(false);
  useEffect(() => {
    if (collectionParam && canFetch && !collectionHandled && !createMutation.isPending) {
      setCollectionHandled(true);
      (async () => {
        try {
          const existing = await conversationsApi.findBySource({ collectionId: collectionParam });
          if (existing.total > 0) {
            router.push(`/chat/${existing.conversations[0].id}`);
            toast({
              title: "Resumed conversation",
              description: existing.conversations[0].title || "Collection conversation",
              action: (
                <ToastAction
                  altText="Start new conversation"
                  onClick={() => {
                    createMutation.mutate(
                      { title: "", options: { collectionId: collectionParam } },
                      { onSuccess: (data) => router.push(`/chat/${data.id}`) }
                    );
                  }}
                >
                  New chat
                </ToastAction>
              ),
            });
            return;
          }
        } catch {
          // Fall through to create
        }
        createMutation.mutate(
          { title: "", options: { collectionId: collectionParam } },
          { onSuccess: (data) => router.push(`/chat/${data.id}`) }
        );
      })();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [collectionParam, canFetch, collectionHandled]);

  // Handle first message — creates conversation then navigates
  const handleFirstMessage = useCallback(async (text: string) => {
    if (createMutation.isPending) return;

    const options: { selectedVideoIds?: string[]; collectionId?: string } = {};
    if (selectedCollectionId) {
      options.collectionId = selectedCollectionId;
    } else if (selectedIds.length > 0) {
      options.selectedVideoIds = selectedIds;
    }

    createMutation.mutate(
      { title: "", options },
      {
        onSuccess: (data) => {
          sessionStorage.setItem(`pending-message-${data.id}`, text);
          setSelectedIds([]);
          setSelectedCollectionId("");
          router.replace(`/chat/${data.id}`);
        },
      }
    );
  }, [createMutation, selectedIds, selectedCollectionId, router]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const text = messageText.trim();
    if (!text) return;
    if (!selectedIds.length && !selectedCollectionId) return;
    setMessageText("");
    handleFirstMessage(text);
  };

  // Show loading state while handling URL params
  if ((sourceParam && !sourceHandled) || (collectionParam && !collectionHandled) || createMutation.isPending) {
    return (
      <div className="flex h-full flex-1 items-center justify-center">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          {sourceParam || collectionParam ? "Loading conversation..." : "Creating conversation..."}
        </div>
      </div>
    );
  }

  const hasSelection = selectedIds.length > 0 || !!selectedCollectionId;

  const suggestedQuestions = hasSelection
    ? selectedIds.length >= 2 || selectedCollectionId
      ? [
          "Compare perspectives across sources",
          "What common themes emerge?",
          "Summarize all sources briefly",
        ]
      : [
          "Summarize the key points",
          "What are the main arguments?",
          "List actionable takeaways",
        ]
    : [];

  return (
    <SourcesPanelProvider
      value={{
        mode: "library",
        libraryItems,
        processingItems,
        selectedIds,
        selectedCollectionId,
        onSelectionChange: setSelectedIds,
        onCollectionChange: setSelectedCollectionId,
        conversationSources: [],
        selectedSourcesCount: 0,
        totalSourcesCount: 0,
        onToggleSource: () => {},
        onSelectAll: () => {},
        onDeselectAll: () => {},
        sourcesUpdatePending: false,
        sourcesUpdateError: null,
        isLoading,
        collections,
      }}
    >
      {/* Chat area + SourcesPanel side by side */}
      <div className="flex flex-1 flex-col min-w-0 min-h-0">
        {/* Mobile header with sources toggle */}
        <header className="flex items-center justify-between h-14 px-4 border-b lg:hidden">
          <h1 className="text-sm font-medium">New chat</h1>
          <SourcesPanelToggle />
        </header>

        {/* Empty state / chat ready area */}
        <div className="flex-1 overflow-y-auto">
          <div className="mx-auto max-w-3xl px-4 py-6">
            <div className="flex h-[60vh] flex-col items-center justify-center gap-4 text-center">
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-primary/10">
                <MessageCircle className="h-6 w-6 text-primary" />
              </div>
              <div className="space-y-1">
                <p className="text-sm font-medium">
                  {hasSelection ? "Ready to chat" : "Select sources to get started"}
                </p>
                <p className="text-xs text-muted-foreground max-w-md">
                  {hasSelection
                    ? "Type a message below to start a conversation with your selected sources."
                    : "Check some sources in the panel on the right, then ask a question."}
                </p>
              </div>

              {/* Suggested questions */}
              {suggestedQuestions.length > 0 && (
                <div className="flex flex-wrap gap-2 justify-center max-w-md">
                  {suggestedQuestions.map((question) => (
                    <Button
                      key={question}
                      variant="outline"
                      size="sm"
                      className="text-xs"
                      onClick={() => {
                        setMessageText("");
                        handleFirstMessage(question);
                      }}
                      disabled={createMutation.isPending}
                    >
                      {question}
                    </Button>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Input area — always visible */}
        <div className="sticky bottom-0 border-t bg-background/95 backdrop-blur">
          <div className="mx-auto max-w-3xl px-4 py-4">
            <form onSubmit={handleSubmit}>
              <div className="flex items-center gap-3">
                <Input
                  placeholder={
                    hasSelection
                      ? "Ask about the content..."
                      : "Select sources first..."
                  }
                  value={messageText}
                  onChange={(e) => setMessageText(e.target.value)}
                  disabled={!hasSelection || createMutation.isPending}
                  className="flex-1 rounded-xl border border-border bg-muted/50 px-4 py-3 text-sm shadow-none focus:border-primary focus:ring-0"
                  autoComplete="off"
                />
                <Button
                  type="submit"
                  size="icon"
                  className="h-10 w-10 rounded-xl bg-primary text-primary-foreground hover:bg-primary/90"
                  disabled={!messageText.trim() || !hasSelection || createMutation.isPending}
                >
                  {createMutation.isPending ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="h-4 w-4">
                      <path d="M3.478 2.405a.75.75 0 00-.926.94l2.432 7.905H13.5a.75.75 0 010 1.5H4.984l-2.432 7.905a.75.75 0 00.926.94 60.519 60.519 0 0018.445-8.986.75.75 0 000-1.218A60.517 60.517 0 003.478 2.405z" />
                    </svg>
                  )}
                </Button>
              </div>
            </form>
          </div>
        </div>
      </div>

      <SourcesPanel />
    </SourcesPanelProvider>
  );
}
