/**
 * Collections Content - SOLID-compliant component
 *
 * Single Responsibility: Display collections list with interactions
 * Open/Closed: Extensible via props
 * Liskov Substitution: Works with any IAuthProvider implementation
 * Interface Segregation: Minimal prop interface
 * Dependency Inversion: Depends on IAuthProvider abstraction
 *
 * Performance: Uses parallel auth + data fetching
 */

"use client";

import { useState, Suspense } from "react";
import Image from "next/image";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Folder, Trash2, Edit, MessageSquare, Video as VideoIcon, MinusCircle } from "lucide-react";
import {
  getCollections,
  deleteCollection,
  getCollection,
  removeVideoFromCollection,
} from "@/lib/api/collections";
import type { Collection, CollectionVideoInfo } from "@/lib/types";
import { CollectionModal } from "./CollectionModal";
import { CollectionAddVideosModal } from "./CollectionAddVideosModal";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";
import { useAuth, useAuthState, createParallelQueryFn } from "@/lib/auth";
import { useSetBreadcrumb } from "@/contexts/BreadcrumbContext";
import Link from "next/link";

/**
 * Collections Content Component
 *
 * Fetches collections in parallel with auth check (non-blocking).
 * Expected performance: ~1-2s instead of 5s.
 */
export function CollectionsContent() {
  const authProvider = useAuth();
  const authState = useAuthState();
  const canFetch = authState.isAuthenticated;
  const queryClient = useQueryClient();

  const [showCreateModal, setShowCreateModal] = useState(false);
  const [editingCollection, setEditingCollection] = useState<Collection | null>(null);
  const [expandedCollectionId, setExpandedCollectionId] = useState<string | null>(null);
  const [collectionForVideoModal, setCollectionForVideoModal] = useState<Collection | null>(null);

  // Performance: Parallel auth + data fetch
  // Auth and getCollections() run concurrently instead of sequentially
  const { data, isLoading, error } = useQuery({
    queryKey: ["collections"],
    queryFn: createParallelQueryFn(authProvider, getCollections),
    staleTime: 2 * 60 * 1000, // 2 minutes
    enabled: canFetch,
  });

  const deleteMutation = useMutation({
    mutationFn: deleteCollection,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["collections"] });
    },
  });

  const removeVideoMutation = useMutation({
    mutationFn: ({ collectionId, videoId }: { collectionId: string; videoId: string }) =>
      removeVideoFromCollection(collectionId, videoId),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ["collection", variables.collectionId] });
      queryClient.invalidateQueries({ queryKey: ["collections"] });
      queryClient.invalidateQueries({ queryKey: ["videos"] });
    },
    onError: (error) => {
      console.error("Failed to remove video from collection:", error);
      alert("Failed to remove video from collection. Please try again.");
    },
  });

  // Parallel fetch expanded collection details
  const { data: expandedCollection } = useQuery({
    queryKey: ["collection", expandedCollectionId],
    queryFn: createParallelQueryFn(authProvider, () => getCollection(expandedCollectionId!)),
    enabled: canFetch && !!expandedCollectionId,
    staleTime: 2 * 60 * 1000,
  });

  const handleDelete = async (id: string, name: string, isDefault: boolean) => {
    if (isDefault) {
      alert("Cannot delete the default 'Uncategorized' collection");
      return;
    }

    if (confirm(`Are you sure you want to delete the collection "${name}"? Videos will not be deleted.`)) {
      try {
        await deleteMutation.mutateAsync(id);
      } catch (err) {
        console.error("Failed to delete collection:", err);
        alert("Failed to delete collection. Please try again.");
      }
    }
  };

  const handleRemoveVideo = async (collection: Collection, video: CollectionVideoInfo) => {
    if (!confirm(`Remove "${video.title}" from "${collection.name}"?`)) {
      return;
    }

    try {
      await removeVideoMutation.mutateAsync({
        collectionId: collection.id,
        videoId: video.id,
      });
    } catch (err) {
      console.error("Failed to remove video from collection:", err);
      alert("Failed to remove video from collection. Please try again.");
    }
  };

  const handleToggleExpand = (collectionId: string) => {
    setExpandedCollectionId(expandedCollectionId === collectionId ? null : collectionId);
  };

  const formatDuration = (seconds: number) => {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    if (hours > 0) {
      return `${hours}h ${minutes}m`;
    }
    return `${minutes}m`;
  };

  const collections = data?.collections ?? [];

  // Breadcrumb: collection count (must be called before early returns)
  const breadcrumbDetail = collections.length > 0 ? `${collections.length} group${collections.length !== 1 ? 's' : ''}` : undefined;
  useSetBreadcrumb("collections", breadcrumbDetail);

  if (!canFetch) {
    return (
      <div className="flex h-64 flex-col items-center justify-center gap-3 text-center text-muted-foreground">
        <p className="text-sm">Sign in to view your collections.</p>
        <div className="flex flex-col gap-2 sm:flex-row">
          <Button asChild>
            <Link href="/sign-up">Create account</Link>
          </Button>
          <Button asChild variant="outline">
            <Link href="/login">Sign in</Link>
          </Button>
        </div>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="flex h-64 items-center justify-center text-muted-foreground">
        Loading collections...
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-64 items-center justify-center text-sm text-destructive">
        Error loading collections: {(error as Error).message}
      </div>
    );
  }

  return (
    <>
      <div className="space-y-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="space-y-1">
            <p className="text-sm font-medium text-muted-foreground">Library organization</p>
            <h1 className="text-3xl font-semibold tracking-tight">Collections</h1>
            <p className="text-sm text-muted-foreground">
              Group related videos by course, instructor, or topic to make retrieval easier.
            </p>
            {collections.length > 0 && (
              <div className="flex items-center gap-2 text-xs text-muted-foreground pt-1">
                <span>{collections.length} collection{collections.length !== 1 ? 's' : ''}</span>
                <span>•</span>
                <span>
                  {collections.reduce((sum, c) => sum + (c.video_count || 0), 0)} video{collections.reduce((sum, c) => sum + (c.video_count || 0), 0) !== 1 ? 's' : ''} total
                </span>
              </div>
            )}
          </div>
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
            <Button variant="outline" size="sm" className="gap-2" disabled>
              <MessageSquare className="h-4 w-4" />
              Coming soon: shared collections
            </Button>
            <Button onClick={() => setShowCreateModal(true)} className="gap-2">
              <Plus className="h-4 w-4" />
              New collection
            </Button>
          </div>
        </div>

        {collections.length === 0 ? (
          <Card className="border-dashed">
            <CardHeader className="flex items-center justify-center text-center">
              <Folder className="mb-3 h-10 w-10 text-muted-foreground" />
              <CardTitle>No collections yet</CardTitle>
              <CardDescription>
                Create your first collection to organize your videos into courses, cohorts, or topics.
              </CardDescription>
            </CardHeader>
            <CardContent className="flex justify-center pb-6">
              <Button onClick={() => setShowCreateModal(true)} className="gap-2">
                <Plus className="h-4 w-4" />
                Create collection
              </Button>
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-4">
            {collections.map((collection) => {
              const isExpanded = expandedCollectionId === collection.id;
              const collectionDetails = isExpanded ? expandedCollection : null;

              return (
                <Card key={collection.id} className="overflow-hidden">
                  <CardHeader className="flex flex-row items-start justify-between gap-4">
                    <div className="flex flex-1 items-start gap-3">
                      <div
                        className={cn(
                          "flex h-9 w-9 items-center justify-center rounded-md border",
                          collection.is_default ? "border-muted text-muted-foreground" : "border-primary/40 text-primary",
                        )}
                      >
                        <Folder className="h-4 w-4" />
                      </div>
                      <div className="space-y-2">
                        <div className="flex flex-wrap items-center gap-2">
                          <h3 className="text-base font-semibold leading-none">
                            {collection.name}
                          </h3>
                          {collection.is_default && (
                            <Badge variant="outline" className="text-xs">
                              Default
                            </Badge>
                          )}
                          {collection.video_count > 0 && (
                            <Badge variant="secondary" className="flex items-center gap-1 text-xs">
                              <VideoIcon className="h-3 w-3" />
                              {collection.video_count} {collection.video_count === 1 ? "video" : "videos"}
                            </Badge>
                          )}
                          {collection.total_duration_seconds > 0 && (
                            <Badge variant="secondary" className="text-xs">
                              {formatDuration(collection.total_duration_seconds)} total
                            </Badge>
                          )}
                        </div>
                        {collection.description && (
                          <p className="text-sm text-muted-foreground">
                            {collection.description}
                          </p>
                        )}
                        {collection.metadata && Object.keys(collection.metadata).length > 0 && (
                          <div className="flex flex-wrap gap-2 pt-1">
                            {collection.metadata.instructor && (
                              <Badge variant="outline" className="text-xs">
                                Instructor: {collection.metadata.instructor}
                              </Badge>
                            )}
                            {collection.metadata.subject && (
                              <Badge variant="outline" className="text-xs">
                                Subject: {collection.metadata.subject}
                              </Badge>
                            )}
                            {collection.metadata.semester && (
                              <Badge variant="outline" className="text-xs">
                                Semester: {collection.metadata.semester}
                              </Badge>
                            )}
                            {collection.metadata.tags?.map((tag: string) => (
                              <Badge key={tag} variant="secondary" className="text-xs">
                                #{tag}
                              </Badge>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                    <div className="flex flex-col items-end gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        className="gap-1"
                        onClick={() => handleToggleExpand(collection.id)}
                      >
                        {isExpanded ? "Hide videos" : "Show videos"}
                      </Button>
                      {!collection.is_default && (
                        <div className="flex gap-1">
                          <Button
                            variant="ghost"
                            size="icon"
                            className="text-muted-foreground hover:text-foreground"
                            onClick={() => setEditingCollection(collection)}
                            title="Edit collection"
                          >
                            <Edit className="h-4 w-4" />
                            <span className="sr-only">Edit collection</span>
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="text-muted-foreground hover:text-destructive"
                            onClick={() => handleDelete(collection.id, collection.name, collection.is_default)}
                            title="Delete collection"
                          >
                            <Trash2 className="h-4 w-4" />
                            <span className="sr-only">Delete collection</span>
                          </Button>
                        </div>
                      )}
                    </div>
                  </CardHeader>

                  {isExpanded && collectionDetails && (
                    <>
                      <Separator />
                      <CardContent className="bg-muted/40">
                        <div className="space-y-3 pt-3">
                          <div className="flex items-center justify-between gap-4">
                            <p className="text-sm font-medium text-foreground">
                              Videos in this collection
                            </p>
                            <Button
                              variant="outline"
                              size="sm"
                              className="gap-1"
                              onClick={() => setCollectionForVideoModal(collection)}
                            >
                              <Plus className="h-3 w-3" />
                              Add videos
                            </Button>
                          </div>
                          {collectionDetails.videos.length === 0 ? (
                            <p className="text-center text-sm text-muted-foreground">
                              No videos in this collection yet.
                            </p>
                          ) : (
                            <div className="space-y-2">
                              {collectionDetails.videos.map((video) => (
                                <div
                                  key={video.id}
                                  className="flex items-center justify-between rounded-md border bg-background p-3"
                                >
                                  <div className="flex flex-1 items-center gap-3">
                                    {video.thumbnail_url && (
                                      <Image
                                        src={video.thumbnail_url}
                                        alt={video.title}
                                        width={80}
                                        height={48}
                                        className="h-12 w-20 rounded object-cover"
                                        unoptimized
                                      />
                                    )}
                                    <div className="min-w-0 flex-1">
                                      <p className="truncate text-sm font-medium text-foreground">
                                        {video.title}
                                      </p>
                                      <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                                        {video.duration_seconds && (
                                          <span>{formatDuration(video.duration_seconds)}</span>
                                        )}
                                        {video.status && (
                                          <span className="capitalize">
                                            Status: {video.status}
                                          </span>
                                        )}
                                        {video.tags && video.tags.length > 0 && (
                                          <span className="flex flex-wrap gap-1">
                                            {video.tags.map((tag) => (
                                              <Badge
                                                key={tag}
                                                variant="secondary"
                                                className="text-[11px]"
                                              >
                                                #{tag}
                                              </Badge>
                                            ))}
                                          </span>
                                        )}
                                      </div>
                                    </div>
                                  </div>
                                  <Button
                                    variant="ghost"
                                    size="icon"
                                    className="text-muted-foreground hover:text-destructive"
                                    onClick={() => handleRemoveVideo(collection, video)}
                                    disabled={removeVideoMutation.isPending}
                                    title="Remove video from collection"
                                  >
                                    <MinusCircle className="h-4 w-4" />
                                    <span className="sr-only">Remove video</span>
                                  </Button>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      </CardContent>
                    </>
                  )}
                </Card>
              );
            })}
          </div>
        )}
      </div>

      {collectionForVideoModal &&
        expandedCollectionId === collectionForVideoModal.id &&
        expandedCollection && (
          <CollectionAddVideosModal
            open
            collectionId={collectionForVideoModal.id}
            collectionName={collectionForVideoModal.name}
            existingVideoIds={expandedCollection.videos.map((video) => video.id)}
            onClose={() => setCollectionForVideoModal(null)}
          />
        )}

      {(showCreateModal || editingCollection) && (
        <CollectionModal
          collection={editingCollection}
          onClose={() => {
            setShowCreateModal(false);
            setEditingCollection(null);
          }}
        />
      )}
    </>
  );
}

/**
 * Collections Content with Suspense Boundary
 *
 * Progressive rendering: Shows loading state while fetching
 */
export function CollectionsContentWithSuspense() {
  return (
    <Suspense
      fallback={
        <div className="flex h-64 items-center justify-center text-muted-foreground">
          Loading collections...
        </div>
      }
    >
      <CollectionsContent />
    </Suspense>
  );
}
