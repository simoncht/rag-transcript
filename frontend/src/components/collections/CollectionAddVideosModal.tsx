"use client";

import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { addVideosToCollection } from "@/lib/api/collections";
import { videosApi } from "@/lib/api/videos";
import type { Video } from "@/lib/types";

const EMPTY_VIDEOS: Video[] = [];

interface CollectionAddVideosModalProps {
  open: boolean;
  collectionId: string;
  collectionName: string;
  existingVideoIds: string[];
  onClose: () => void;
}

export function CollectionAddVideosModal({
  open,
  collectionId,
  collectionName,
  existingVideoIds,
  onClose,
}: CollectionAddVideosModalProps) {
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedVideoIds, setSelectedVideoIds] = useState<Set<string>>(new Set());
  const [error, setError] = useState("");
  const queryClient = useQueryClient();

  const { data, isLoading, error: queryError } = useQuery({
    queryKey: ["videos-completed-for-collection"],
    queryFn: () => videosApi.list(0, 100, "completed"),
    enabled: open,
    staleTime: 0, // Always fetch fresh data when modal opens
  });

  const addMutation = useMutation({
    mutationFn: (videoIds: string[]) => addVideosToCollection(collectionId, { video_ids: videoIds }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["collection", collectionId] });
      queryClient.invalidateQueries({ queryKey: ["collections"] });
      queryClient.invalidateQueries({ queryKey: ["videos"] });
      setSelectedVideoIds(new Set());
      setSearchTerm("");
      setError("");
      onClose();
    },
    onError: (err: any) => {
      const message = err?.response?.data?.detail ?? "Failed to add videos to collection";
      setError(message);
    },
  });

  useEffect(() => {
    if (open) {
      setSelectedVideoIds(new Set());
      setSearchTerm("");
      setError("");
    }
  }, [open]);

  const videos = data?.videos ?? EMPTY_VIDEOS;

  const normalizedSearch = searchTerm.trim().toLowerCase();
  const filteredVideos = useMemo(() => {
    if (!normalizedSearch) return videos;
    return videos.filter((video) => video.title.toLowerCase().includes(normalizedSearch));
  }, [normalizedSearch, videos]);

  const selectedCount = selectedVideoIds.size;

  const handleToggle = (videoId: string) => {
    setSelectedVideoIds((prev) => {
      const next = new Set(prev);
      if (next.has(videoId)) {
        next.delete(videoId);
      } else {
        next.add(videoId);
      }
      return next;
    });
  };

  const handleAdd = () => {
    if (selectedCount === 0) return;
    addMutation.mutate(Array.from(selectedVideoIds));
  };

  const formatDuration = (seconds?: number | null) => {
    if (!seconds) {
      return "0m";
    }
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    if (hours > 0) {
      return `${hours}h ${minutes}m`;
    }
    return `${minutes}m`;
  };

  return (
    <Dialog open={open} onOpenChange={(isOpen) => !isOpen && onClose()}>
      <DialogContent className="max-w-3xl">
        <DialogHeader>
          <DialogTitle>Add videos to {collectionName}</DialogTitle>
          <DialogDescription>
            Search your library and select videos to include in this collection.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <Input
            placeholder="Search videos"
            value={searchTerm}
            onChange={(event) => setSearchTerm(event.target.value)}
            disabled={isLoading}
          />
          <div className="max-h-[60vh] space-y-2 overflow-y-auto pr-1">
            {isLoading ? (
              <div className="py-8 text-center text-sm text-muted-foreground">
                Loading videos...
              </div>
            ) : queryError ? (
              <div className="py-8 text-center text-sm text-destructive">
                Failed to load videos. Please try again.
              </div>
            ) : filteredVideos.length === 0 ? (
              <div className="py-8 text-center text-sm text-muted-foreground">
                {videos.length === 0
                  ? "No completed videos yet. Videos are ready to add once processing finishes."
                  : "No videos were found for that search term."}
              </div>
            ) : (
              filteredVideos.map((video) => {
                const alreadyAdded = existingVideoIds.includes(video.id);
                const checkboxId = `collection-add-${collectionId}-${video.id}`;
                const isSelected = selectedVideoIds.has(video.id);

                return (
                  <label
                    key={video.id}
                    htmlFor={checkboxId}
                    className={`flex flex-col rounded-lg border p-3 transition ${
                      alreadyAdded
                        ? "cursor-default border-green-200 bg-green-50/50"
                        : "cursor-pointer hover:border-primary/60"
                    }`}
                  >
                    <div className="flex items-center justify-between gap-3">
                      <div className="flex items-center gap-3">
                        <Checkbox
                          id={checkboxId}
                          checked={alreadyAdded || isSelected}
                          onCheckedChange={(checked) => {
                            if (alreadyAdded) return;
                            if (checked) {
                              setSelectedVideoIds((prev) => new Set(prev).add(video.id));
                            } else {
                              setSelectedVideoIds((prev) => {
                                const next = new Set(prev);
                                next.delete(video.id);
                                return next;
                              });
                            }
                          }}
                          disabled={alreadyAdded || addMutation.isPending}
                          className={alreadyAdded ? "opacity-50" : ""}
                        />
                        <div className="min-w-0 flex-1">
                          <p className={`text-sm font-medium ${alreadyAdded ? "text-muted-foreground" : "text-foreground"}`}>
                            {video.title}
                          </p>
                          <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                            <span>{formatDuration(video.duration_seconds)}</span>
                          </div>
                        </div>
                      </div>
                      {alreadyAdded && (
                        <Badge variant="outline" className="shrink-0 whitespace-nowrap border-green-300 bg-green-100 text-xs text-green-700">
                          Added
                        </Badge>
                      )}
                    </div>
                    {video.tags.length > 0 && (
                      <div className="mt-3 flex flex-wrap gap-2 pl-7">
                        {video.tags.map((tag) => (
                          <Badge key={tag} variant="secondary" className="text-[11px]">
                            #{tag}
                          </Badge>
                        ))}
                      </div>
                    )}
                  </label>
                );
              })
            )}
          </div>
          {error && (
            <p className="text-sm text-destructive">{error}</p>
          )}
        </div>

        <DialogFooter className="items-center justify-between gap-2">
          <p className="text-sm text-muted-foreground">
            {selectedCount === 0
              ? "Select videos to add to the collection."
              : `${selectedCount} video${selectedCount === 1 ? "" : "s"} ready to add.`}
          </p>
          <div className="flex gap-2">
            <Button variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button
              onClick={handleAdd}
              disabled={selectedCount === 0 || addMutation.isPending}
            >
              {addMutation.isPending
                ? "Adding..."
                : selectedCount === 0
                ? "Add to collection"
                : `Add ${selectedCount} video${selectedCount === 1 ? "" : "s"}`}
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
