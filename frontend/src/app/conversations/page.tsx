"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { formatDistanceToNow } from "date-fns";
import { useAuth } from "@clerk/nextjs";
import { MainLayout } from "@/components/layout/MainLayout";
import { conversationsApi } from "@/lib/api/conversations";
import { videosApi } from "@/lib/api/videos";
import { getCollections } from "@/lib/api/collections";
import { Plus, Trash2, MessageSquare, Loader2, Folder } from "lucide-react";
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

type SelectionMode = "collection" | "custom";

export default function ConversationsPage() {
  const { isLoaded, isSignedIn } = useAuth();
  const canFetch = isLoaded && isSignedIn;
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [title, setTitle] = useState("");
  const [selectionMode, setSelectionMode] = useState<SelectionMode>("collection");
  const [selectedCollectionId, setSelectedCollectionId] = useState("");
  const [selectedVideoIds, setSelectedVideoIds] = useState<string[]>([]);

  const queryClient = useQueryClient();
  const router = useRouter();

  const { data: conversationsData, isLoading: conversationsLoading } = useQuery({
    queryKey: ["conversations"],
    queryFn: () => conversationsApi.list(),
    enabled: canFetch,
  });

  const { data: videosData } = useQuery({
    queryKey: ["videos"],
    queryFn: () => videosApi.list(),
    enabled: canFetch && showCreateForm && selectionMode === "custom",
  });

  const { data: collectionsData } = useQuery({
    queryKey: ["collections"],
    queryFn: getCollections,
    enabled: canFetch && showCreateForm && selectionMode === "collection",
  });

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

  const createErrorMessage = createMutation.isError
    ? createMutation.error instanceof Error
      ? createMutation.error.message
      : "Unable to create conversation. Please check your session and try again."
    : null;

  const deleteMutation = useMutation({
    mutationFn: conversationsApi.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["conversations"] });
    },
  });

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

  return (
    <MainLayout>
      <div className="space-y-6">
        <div className="space-y-1">
          <p className="text-sm font-medium text-muted-foreground">Transcript chat</p>
          <h1 className="text-3xl font-semibold tracking-tight">Conversations</h1>
          <p className="text-sm text-muted-foreground">
            Create focused chats over one or more videos and pick up where you left off.
          </p>
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
                          videos.
                        </p>
                        <div className="mt-2">
                          <Label htmlFor="collection" className="text-xs">
                            Collection
                          </Label>
                          <select
                            id="collection"
                            className="mt-1 w-full rounded-md border bg-background px-3 py-2 text-sm"
                            value={selectedCollectionId}
                            onChange={(e) => setSelectedCollectionId(e.target.value)}
                          >
                            <option value="">Select a collection</option>
                            {collectionsData?.collections.map((collection) => (
                              <option key={collection.id} value={collection.id}>
                                {collection.name} ({collection.video_count} videos)
                              </option>
                            ))}
                          </select>
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
                          Choose individual completed videos for a focused study session or cross-topic
                          review.
                        </p>
                        <div className="mt-2 max-h-48 space-y-2 overflow-y-auto rounded-md border bg-muted/40 p-2">
                          {completedVideos.length === 0 ? (
                            <p className="px-1 py-2 text-xs text-muted-foreground">
                              No completed videos yet. Ingest and process videos on the Videos page first.
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
              ) : (
                <div className="divide-y rounded-md border bg-muted/20">
                  {conversationsData?.conversations.map((conversation) => (
                    <button
                      key={conversation.id}
                      type="button"
                      className="flex w-full items-center justify-between gap-4 px-4 py-3 text-left hover:bg-muted/60"
                      onClick={() => router.push(`/conversations/${conversation.id}`)}
                    >
                      <div className="flex-1">
                        <p className="text-sm font-medium text-foreground">
                          {conversation.title}
                        </p>
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
                                  new Date(conversation.last_message_at),
                                )} ago`
                              : `Created ${formatDistanceToNow(
                                  new Date(conversation.created_at),
                                )} ago`}
                          </span>
                        </div>
                      </div>
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        className="text-muted-foreground hover:text-destructive"
                        onClick={(e) => {
                          e.stopPropagation();
                          deleteMutation.mutate(conversation.id);
                        }}
                        disabled={deleteMutation.isPending}
                      >
                        <Trash2 className="h-4 w-4" />
                        <span className="sr-only">Delete conversation</span>
                      </Button>
                    </button>
                  ))}
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    </MainLayout>
  );
}
