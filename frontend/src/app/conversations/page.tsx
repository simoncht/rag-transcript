"use client";

import { Suspense, useState, useEffect, useMemo } from "react";
import { useQuery, useMutation, useQueryClient, keepPreviousData } from "@tanstack/react-query";
import { useRouter, useSearchParams } from "next/navigation";
import { formatDistanceToNow } from "date-fns";
import { parseUTCDate } from "@/lib/utils";
import { useAuthState } from "@/lib/auth";
import { useSetBreadcrumb } from "@/contexts/BreadcrumbContext";
import { MainLayout } from "@/components/layout/MainLayout";
import { conversationsApi } from "@/lib/api/conversations";
import { videosApi } from "@/lib/api/videos";
import { getCollections } from "@/lib/api/collections";
import { Plus, MessageSquare, Loader2, Folder, Search } from "lucide-react";
import { usePaginationParams } from "@/hooks/usePaginationParams";
import { PaginationBar } from "@/components/shared/PaginationBar";
import { useToast } from "@/hooks/use-toast";
import { ToastAction } from "@/components/ui/toast";
import { ConversationActionsMenu } from "@/components/conversations/ConversationActionsMenu";
import { InlineRenameInput } from "@/components/conversations/InlineRenameInput";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import Link from "next/link";

type SelectionMode = "collection" | "custom";

export default function ConversationsPage() {
  return (
    <Suspense>
      <ConversationsPageContent />
    </Suspense>
  );
}

function ConversationsPageContent() {
  const authState = useAuthState();
  const canFetch = authState.isAuthenticated;
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [title, setTitle] = useState("");
  const [selectionMode, setSelectionMode] = useState<SelectionMode>("collection");
  const [selectedCollectionId, setSelectedCollectionId] = useState("");
  const [selectedVideoIds, setSelectedVideoIds] = useState<string[]>([]);
  const [renamingListId, setRenamingListId] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [sortOrder, setSortOrder] = useState<"recent" | "messages" | "alpha">("recent");

  const { page, pageSize, skip, setPage, setPageSize } = usePaginationParams();
  const queryClient = useQueryClient();
  const router = useRouter();
  const searchParams = useSearchParams();
  const sourceParam = searchParams.get("source");
  const { toast } = useToast();

  const { data: conversationsData, isLoading: conversationsLoading, isFetching } = useQuery({
    queryKey: ["conversations", { page, pageSize }],
    queryFn: () => conversationsApi.list(skip, pageSize),
    enabled: canFetch,
    placeholderData: keepPreviousData,
  });

  const { data: videosData } = useQuery({
    queryKey: ["videos"],
    queryFn: () => videosApi.list(),
    enabled: canFetch && showCreateForm && selectionMode === "custom",
  });

  const { data: collectionsData, isLoading: collectionsLoading } = useQuery({
    queryKey: ["collections"],
    queryFn: () => getCollections(),
    enabled: canFetch && showCreateForm,
  });

  // Auto-switch to custom mode if no collections exist
  useEffect(() => {
    if (showCreateForm && collectionsData && collectionsData.collections.length === 0) {
      setSelectionMode("custom");
    }
  }, [showCreateForm, collectionsData]);

  const createMutation = useMutation({
    mutationFn: ({
      title,
      options,
    }: {
      title: string;
      options: { selectedVideoIds?: string[]; collectionId?: string };
    }) => conversationsApi.create(title, options),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["conversations"] });
      setTitle("");
      setSelectedVideoIds([]);
      setSelectedCollectionId("");
      setShowCreateForm(false);
      router.push(`/conversations/${data.id}`);
    },
  });

  // Auto-resume or create conversation when ?source=<id> is present (from "Chat with this document/video")
  const [sourceHandled, setSourceHandled] = useState(false);
  useEffect(() => {
    if (sourceParam && canFetch && !sourceHandled && !createMutation.isPending) {
      setSourceHandled(true);
      (async () => {
        try {
          const existing = await conversationsApi.findBySource({ videoId: sourceParam });
          if (existing.total > 0) {
            router.push(`/conversations/${existing.conversations[0].id}`);
            toast({
              title: "Resumed conversation",
              description: existing.conversations[0].title || "Previous conversation",
              action: (
                <ToastAction
                  altText="Start new conversation"
                  onClick={() => {
                    createMutation.mutate({ title: "", options: { selectedVideoIds: [sourceParam] } });
                  }}
                >
                  New chat
                </ToastAction>
              ),
            });
            return;
          }
        } catch {
          // Fall through to create on lookup failure
        }
        createMutation.mutate({ title: "", options: { selectedVideoIds: [sourceParam] } });
      })();
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sourceParam, canFetch, sourceHandled]);

  const createErrorMessage = createMutation.isError
    ? createMutation.error instanceof Error
      ? createMutation.error.message
      : "Unable to create conversation. Please check your session and try again."
    : null;

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault();
    if (selectionMode === "collection" && selectedCollectionId) {
      createMutation.mutate({ title, options: { collectionId: selectedCollectionId } });
    } else if (selectionMode === "custom" && selectedVideoIds.length > 0) {
      createMutation.mutate({ title, options: { selectedVideoIds } });
    }
  };

  const toggleVideoSelection = (videoId: string) => {
    setSelectedVideoIds((prev) =>
      prev.includes(videoId) ? prev.filter((id) => id !== videoId) : [...prev, videoId],
    );
  };

  const completedVideos =
    videosData?.videos.filter((video) => video.status === "completed") ?? [];

  const resetForm = () => {
    setShowCreateForm(false);
    setTitle("");
    setSelectedVideoIds([]);
    setSelectedCollectionId("");
    setSelectionMode("collection");
  };

  const filteredConversations = useMemo(() => {
    const conversations = conversationsData?.conversations ?? [];
    let filtered = conversations;
    if (searchTerm) {
      const term = searchTerm.toLowerCase();
      filtered = filtered.filter((c) => c.title?.toLowerCase().includes(term));
    }
    return [...filtered].sort((a, b) => {
      if (sortOrder === "messages") return (b.message_count || 0) - (a.message_count || 0);
      if (sortOrder === "alpha") return (a.title || "").localeCompare(b.title || "");
      // "recent" — by last_message_at descending, fallback to created_at
      const aDate = a.last_message_at || a.created_at;
      const bDate = b.last_message_at || b.created_at;
      return new Date(bDate).getTime() - new Date(aDate).getTime();
    });
  }, [conversationsData?.conversations, searchTerm, sortOrder]);

  // Breadcrumb: active conversations count
  const breadcrumbDetail = useMemo(() => {
    const conversations = conversationsData?.conversations;
    if (!conversations || conversations.length === 0) return undefined;
    const activeCount = conversations.filter(c => (c.message_count || 0) > 0).length;
    if (activeCount > 0) return `${activeCount} active`;
    return `${conversations.length} total`;
  }, [conversationsData?.conversations]);

  useSetBreadcrumb("conversations", breadcrumbDetail);

  if (!canFetch) {
    return (
      <MainLayout>
        <Card>
          <CardHeader className="text-center">
            <CardTitle>Sign in to view conversations</CardTitle>
            <CardDescription>Access your chats and start new conversations after signing in.</CardDescription>
          </CardHeader>
          <CardContent className="flex justify-center pb-8">
            <div className="flex flex-col gap-2 sm:flex-row">
              <Button asChild>
                <Link href="/sign-up">Create account</Link>
              </Button>
              <Button asChild variant="outline">
                <Link href="/login">Sign in</Link>
              </Button>
            </div>
          </CardContent>
        </Card>
      </MainLayout>
    );
  }

  return (
    <MainLayout>
      <div className="space-y-6">
        <div className="space-y-1">
          <p className="text-sm font-medium text-muted-foreground">Transcript chat</p>
          <h1 className="text-3xl font-semibold tracking-tight">Conversations</h1>
          <p className="text-sm text-muted-foreground">
            Create focused chats over your content and pick up where you left off.
          </p>
          {conversationsData && (conversationsData.total ?? conversationsData.conversations.length) > 0 && (
            <div className="flex items-center gap-2 text-xs text-muted-foreground pt-1">
              <span>{conversationsData.total ?? conversationsData.conversations.length} conversation{(conversationsData.total ?? conversationsData.conversations.length) !== 1 ? 's' : ''}</span>
              <span>•</span>
              <span>
                {conversationsData.conversations.reduce((sum, c) => sum + (c.message_count || 0), 0)} message{conversationsData.conversations.reduce((sum, c) => sum + (c.message_count || 0), 0) !== 1 ? 's' : ''}
              </span>
              {(() => {
                const dates = conversationsData.conversations
                  .map(c => c.last_message_at)
                  .filter(Boolean)
                  .sort((a, b) => new Date(b!).getTime() - new Date(a!).getTime());
                const lastActivity = dates[0];
                return lastActivity ? (
                  <>
                    <span>•</span>
                    <span>Last active {formatDistanceToNow(parseUTCDate(lastActivity), { addSuffix: true })}</span>
                  </>
                ) : null;
              })()}
            </div>
          )}
        </div>

        <Card>
          <CardHeader className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <CardTitle>Conversations</CardTitle>
              <CardDescription>
                Start a new conversation or jump back into a recent one.
              </CardDescription>
            </div>
            <Button
              onClick={() => setShowCreateForm((prev) => !prev)}
              className="mt-2 gap-2 sm:mt-0"
              variant={showCreateForm ? "outline" : "default"}
            >
              <Plus className="h-4 w-4" />
              {showCreateForm ? "Hide form" : "New conversation"}
            </Button>
          </CardHeader>
          <CardContent className="space-y-6">
            {showCreateForm && (
              <div className="rounded-md border bg-muted/30 p-4">
                <form onSubmit={handleCreate} className="space-y-6">
                  <div className="space-y-2">
                    <Label htmlFor="title">Title (optional)</Label>
                    <Input
                      id="title"
                      type="text"
                      value={title}
                      onChange={(e) => setTitle(e.target.value)}
                      placeholder="e.g. Week 3 problem set review"
                    />
                  </div>

                  <div className="space-y-4">
                    <p className="text-sm font-medium text-foreground">
                      What do you want to chat over?
                    </p>
                    <div className="grid gap-4 md:grid-cols-2">
                      <label
                        className={`flex cursor-pointer flex-col gap-2 rounded-md border p-4 ${
                          selectionMode === "collection"
                            ? "border-primary bg-primary/5"
                            : "border-border bg-background"
                        }`}
                      >
                        <div className="flex items-center justify-between gap-2">
                          <div className="flex items-center gap-2">
                            <input
                              type="radio"
                              name="selection-mode"
                              value="collection"
                              checked={selectionMode === "collection"}
                              onChange={() => setSelectionMode("collection")}
                              className="h-4 w-4"
                            />
                            <span className="text-sm font-medium">Collection</span>
                          </div>
                          <Badge variant="outline" className="gap-1">
                            <Folder className="h-3 w-3" />
                            Best for courses
                          </Badge>
                        </div>
                        <p className="text-xs text-muted-foreground">
                          Pick an existing collection (like a course or topic) and chat over all of its
                          content.
                        </p>
                        <div className="mt-2">
                          <Label htmlFor="collection" className="text-xs">
                            Collection
                          </Label>
                          {collectionsLoading ? (
                            <p className="mt-1 text-xs text-muted-foreground">Loading collections...</p>
                          ) : collectionsData?.collections.length === 0 ? (
                            <p className="mt-1 text-xs text-muted-foreground">
                              No collections yet.{" "}
                              <Link href="/collections" className="text-primary hover:underline">
                                Create one
                              </Link>{" "}
                              to organize related content, or switch to Custom selection below.
                            </p>
                          ) : (
                            <select
                              id="collection"
                              className="mt-1 w-full rounded-md border bg-background px-3 py-2 text-sm"
                              value={selectedCollectionId}
                              onChange={(e) => setSelectedCollectionId(e.target.value)}
                            >
                              <option value="">Select a collection</option>
                              {collectionsData?.collections.map((collection) => (
                                <option key={collection.id} value={collection.id}>
                                  {collection.name} ({collection.video_count} items)
                                </option>
                              ))}
                            </select>
                          )}
                        </div>
                      </label>

                      <label
                        className={`flex cursor-pointer flex-col gap-2 rounded-md border p-4 ${
                          selectionMode === "custom"
                            ? "border-primary bg-primary/5"
                            : "border-border bg-background"
                        }`}
                      >
                        <div className="flex items-center justify-between gap-2">
                          <div className="flex items-center gap-2">
                            <input
                              type="radio"
                              name="selection-mode"
                              value="custom"
                              checked={selectionMode === "custom"}
                              onChange={() => setSelectionMode("custom")}
                              className="h-4 w-4"
                            />
                            <span className="text-sm font-medium">Custom selection</span>
                          </div>
                          <Badge variant="outline" className="gap-1">
                            <MessageSquare className="h-3 w-3" />
                            Mix &amp; match
                          </Badge>
                        </div>
                        <p className="text-xs text-muted-foreground">
                          Choose individual completed content for a focused study session or cross-topic
                          review.
                        </p>
                        <div className="mt-2 max-h-48 space-y-2 overflow-y-auto rounded-md border bg-muted/40 p-2">
                          {completedVideos.length === 0 ? (
                            <p className="px-1 py-2 text-xs text-muted-foreground">
                              No completed content yet.{" "}
                              <Link href="/videos" className="text-primary hover:underline">
                                Add a video
                              </Link>{" "}
                              to get started.
                            </p>
                          ) : (
                            completedVideos.map((video) => (
                              <label
                                key={video.id}
                                className="flex cursor-pointer items-center gap-2 rounded-md px-2 py-1 text-xs hover:bg-muted"
                              >
                                <Checkbox
                                  checked={selectedVideoIds.includes(video.id)}
                                  onCheckedChange={() => toggleVideoSelection(video.id)}
                                />
                                <span className="line-clamp-2 flex-1">{video.title}</span>
                              </label>
                            ))
                          )}
                        </div>
                      </label>
                    </div>
                  </div>

                  {createErrorMessage && (
                    <p className="text-sm text-destructive">{createErrorMessage}</p>
                  )}

                  <div className="flex justify-end gap-2">
                    <Button type="button" variant="outline" onClick={resetForm}>
                      Cancel
                    </Button>
                    <Button
                      type="submit"
                      disabled={
                        createMutation.isPending ||
                        (selectionMode === "collection" && !selectedCollectionId) ||
                        (selectionMode === "custom" && selectedVideoIds.length === 0)
                      }
                      className="gap-2"
                    >
                      {createMutation.isPending && (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      )}
                      Create conversation
                    </Button>
                  </div>
                </form>
              </div>
            )}

            <div className="space-y-3">
              <div>
                <p className="text-sm font-medium text-foreground">Recent conversations</p>
                <p className="text-xs text-muted-foreground">
                  Jump back into ongoing threads or clean up old ones.
                </p>
              </div>

              {conversationsData?.conversations && conversationsData.conversations.length > 0 && (
                <div className="flex items-center gap-2">
                  <div className="relative flex-1">
                    <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                    <Input
                      placeholder="Search conversations..."
                      value={searchTerm}
                      onChange={(e) => setSearchTerm(e.target.value)}
                      className="pl-8 h-9"
                    />
                  </div>
                  <select
                    value={sortOrder}
                    onChange={(e) => setSortOrder(e.target.value as "recent" | "messages" | "alpha")}
                    className="h-9 w-[140px] rounded-md border border-border bg-background px-3 text-sm"
                  >
                    <option value="recent">Most recent</option>
                    <option value="messages">Most messages</option>
                    <option value="alpha">Alphabetical</option>
                  </select>
                </div>
              )}

              {conversationsLoading ? (
                <div className="flex items-center justify-center py-8 text-muted-foreground">
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Loading conversations...
                </div>
              ) : conversationsData?.conversations.length === 0 ? (
                <div className="flex flex-col items-center justify-center gap-2 rounded-md border border-dashed py-10 text-center">
                  <MessageSquare className="h-10 w-10 text-muted-foreground" />
                  <p className="text-sm font-medium text-foreground">No conversations yet</p>
                  <p className="text-xs text-muted-foreground">
                    Start by creating a new conversation above.
                  </p>
                </div>
              ) : filteredConversations.length === 0 ? (
                <div className="flex flex-col items-center justify-center gap-2 rounded-md border border-dashed py-10 text-center">
                  <Search className="h-10 w-10 text-muted-foreground" />
                  <p className="text-sm font-medium text-foreground">No matching conversations</p>
                  <p className="text-xs text-muted-foreground">
                    Try a different search term.
                  </p>
                </div>
              ) : (
                <div className={`divide-y rounded-md border bg-muted/20 transition-opacity ${isFetching && !conversationsLoading ? "opacity-60" : ""}`}>
                  {filteredConversations.map((conversation) => (
                    <button
                      key={conversation.id}
                      type="button"
                      className="flex w-full items-center justify-between gap-4 px-4 py-3 text-left hover:bg-muted/60"
                      onClick={() => {
                        if (renamingListId === conversation.id) return;
                        router.push(`/conversations/${conversation.id}`);
                      }}
                    >
                      <div className="flex-1 min-w-0">
                        {renamingListId === conversation.id ? (
                          <InlineRenameInput
                            conversationId={conversation.id}
                            currentTitle={conversation.title}
                            onComplete={() => setRenamingListId(null)}
                            className="h-8 text-sm"
                          />
                        ) : (
                          <p className="text-sm font-medium text-foreground truncate">
                            {conversation.title}
                          </p>
                        )}
                        {conversation.last_message_preview && (
                          <p className="mt-0.5 text-xs text-muted-foreground line-clamp-1">
                            {conversation.last_message_preview}
                          </p>
                        )}
                        <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                          <span>
                            {conversation.message_count} message
                            {conversation.message_count !== 1 ? "s" : ""}
                          </span>
                          <span>
                            {conversation.selected_video_ids.length} video
                            {conversation.selected_video_ids.length !== 1 ? "s" : ""}
                          </span>
                          <span>
                            {conversation.last_message_at
                              ? `Active ${formatDistanceToNow(
                                  parseUTCDate(conversation.last_message_at),
                                )} ago`
                              : `Created ${formatDistanceToNow(
                                  parseUTCDate(conversation.created_at),
                                )} ago`}
                          </span>
                        </div>
                      </div>
                      <ConversationActionsMenu
                        conversationId={conversation.id}
                        currentTitle={conversation.title}
                        variant="list"
                        onRenameStart={() => setRenamingListId(conversation.id)}
                      />
                    </button>
                  ))}
                </div>
              )}

              {conversationsData && (conversationsData.total ?? 0) > 0 && (
                <PaginationBar
                  page={page}
                  pageSize={pageSize}
                  total={conversationsData.total ?? conversationsData.conversations.length}
                  onPageChange={setPage}
                  onPageSizeChange={setPageSize}
                  isLoading={isFetching}
                  itemLabel="conversations"
                />
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    </MainLayout>
  );
}
