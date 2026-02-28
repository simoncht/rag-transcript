"use client";

import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { CheckSquare, Square, MinusSquare, Video as VideoIcon, FileText } from "lucide-react";
import { addContentToCollection } from "@/lib/api/collections";
import { videosApi } from "@/lib/api/videos";
import { contentApi } from "@/lib/api/content";
import { getContentTypeLabel, getContentTypeBadgeClass, formatFileSize } from "@/lib/content-type-utils";
import type { Video, ContentItem } from "@/lib/types";
import { cn } from "@/lib/utils";

const EMPTY_VIDEOS: Video[] = [];

interface UnifiedContentItem {
  id: string;
  title: string;
  contentType: string;
  duration_seconds?: number;
  page_count?: number;
  file_size_bytes?: number;
  tags: string[];
}

interface CollectionAddContentModalProps {
  open: boolean;
  collectionId: string;
  collectionName: string;
  existingItemIds: string[];
  onClose: () => void;
}

export function CollectionAddContentModal({
  open,
  collectionId,
  collectionName,
  existingItemIds,
  onClose,
}: CollectionAddContentModalProps) {
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [error, setError] = useState("");
  const queryClient = useQueryClient();

  const { data, isLoading: videosLoading, error: queryError } = useQuery({
    queryKey: ["videos-completed-for-collection"],
    queryFn: () => videosApi.list(0, 100, "completed"),
    enabled: open,
    staleTime: 0,
  });

  const { data: documentsData, isLoading: docsLoading } = useQuery({
    queryKey: ["documents-completed-for-collection"],
    queryFn: () => contentApi.list(0, 100, undefined, "completed"),
    enabled: open,
    staleTime: 0,
  });

  const isLoading = videosLoading || docsLoading;

  const addMutation = useMutation({
    mutationFn: (videoIds: string[]) => addContentToCollection(collectionId, { video_ids: videoIds }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["collection", collectionId] });
      queryClient.invalidateQueries({ queryKey: ["collections"] });
      queryClient.invalidateQueries({ queryKey: ["videos"] });
      setSelectedIds(new Set());
      setSearchTerm("");
      setError("");
      onClose();
    },
    onError: (err: any) => {
      const message = err?.response?.data?.detail ?? "Failed to add content to collection";
      setError(message);
    },
  });

  useEffect(() => {
    if (open) {
      setSelectedIds(new Set());
      setSearchTerm("");
      setError("");
    }
  }, [open]);

  const videos = data?.videos ?? EMPTY_VIDEOS;
  const documents = documentsData?.items ?? [];

  // Merge videos + documents into unified list
  const allContent: UnifiedContentItem[] = useMemo(() => {
    const videoItems: UnifiedContentItem[] = videos.map((v) => ({
      id: v.id,
      title: v.title,
      contentType: "youtube",
      duration_seconds: v.duration_seconds,
      tags: v.tags || [],
    }));
    const docItems: UnifiedContentItem[] = documents.map((d) => ({
      id: d.id,
      title: d.title,
      contentType: d.content_type,
      page_count: d.page_count ?? undefined,
      file_size_bytes: d.file_size_bytes ?? undefined,
      tags: [],
    }));
    return [...videoItems, ...docItems];
  }, [videos, documents]);

  const normalizedSearch = searchTerm.trim().toLowerCase();
  const filteredContent = useMemo(() => {
    if (!normalizedSearch) return allContent;
    return allContent.filter((item) => item.title.toLowerCase().includes(normalizedSearch));
  }, [normalizedSearch, allContent]);

  // Get items that can be selected (not already in collection)
  const selectableItems = useMemo(() => {
    return filteredContent.filter((item) => !existingItemIds.includes(item.id));
  }, [filteredContent, existingItemIds]);

  // Check selection state for the toggle button
  const allSelectableSelected = selectableItems.length > 0 &&
    selectableItems.every((item) => selectedIds.has(item.id));
  const someSelected = selectableItems.some((item) => selectedIds.has(item.id));
  const selectionState: "all" | "some" | "none" = allSelectableSelected
    ? "all"
    : someSelected
    ? "some"
    : "none";

  const handleSelectAll = () => {
    if (allSelectableSelected) {
      // Deselect all selectable items
      setSelectedIds((prev) => {
        const next = new Set(prev);
        selectableItems.forEach((item) => next.delete(item.id));
        return next;
      });
    } else {
      // Select all selectable items
      setSelectedIds((prev) => {
        const next = new Set(prev);
        selectableItems.forEach((item) => next.add(item.id));
        return next;
      });
    }
  };

  const selectedCount = selectedIds.size;

  const handleToggle = (videoId: string) => {
    setSelectedIds((prev) => {
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
    addMutation.mutate(Array.from(selectedIds));
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
          <DialogTitle>Add content to {collectionName}</DialogTitle>
          <DialogDescription>
            Search your library and select videos or documents to include in this collection.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <Input
            placeholder="Search videos and documents..."
            value={searchTerm}
            onChange={(event) => setSearchTerm(event.target.value)}
            disabled={isLoading}
          />

          {/* Select All / Deselect All Toggle */}
          {!isLoading && !queryError && selectableItems.length > 0 && (
            <div className="flex items-center justify-between rounded-lg border bg-muted/30 px-3 py-2">
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <span className="font-medium text-foreground">{selectableItems.length}</span>
                <span>item{selectableItems.length === 1 ? "" : "s"} available</span>
                {selectedCount > 0 && (
                  <>
                    <span className="text-muted-foreground/50">•</span>
                    <span className="font-medium text-primary">{selectedCount} selected</span>
                  </>
                )}
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={handleSelectAll}
                disabled={addMutation.isPending}
                className="gap-2 text-sm font-medium"
              >
                {selectionState === "all" ? (
                  <>
                    <CheckSquare className="h-4 w-4 text-primary" />
                    Deselect All
                  </>
                ) : selectionState === "some" ? (
                  <>
                    <MinusSquare className="h-4 w-4 text-primary" />
                    Select All
                  </>
                ) : (
                  <>
                    <Square className="h-4 w-4" />
                    Select All
                  </>
                )}
              </Button>
            </div>
          )}

          <div className="max-h-[60vh] space-y-2 overflow-y-auto pr-1">
            {isLoading ? (
              <div className="py-8 text-center text-sm text-muted-foreground">
                Loading content...
              </div>
            ) : queryError ? (
              <div className="py-8 text-center text-sm text-destructive">
                Failed to load content. Please try again.
              </div>
            ) : filteredContent.length === 0 ? (
              <div className="py-8 text-center text-sm text-muted-foreground">
                {allContent.length === 0
                  ? "No completed content yet. Videos and documents are ready to add once processing finishes."
                  : "No content was found for that search term."}
              </div>
            ) : (
              filteredContent.map((item) => {
                const alreadyAdded = existingItemIds.includes(item.id);
                const checkboxId = `collection-add-${collectionId}-${item.id}`;
                const isSelected = selectedIds.has(item.id);
                const isDocument = item.contentType !== "youtube";

                return (
                  <label
                    key={item.id}
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
                              setSelectedIds((prev) => new Set(prev).add(item.id));
                            } else {
                              setSelectedIds((prev) => {
                                const next = new Set(prev);
                                next.delete(item.id);
                                return next;
                              });
                            }
                          }}
                          disabled={alreadyAdded || addMutation.isPending}
                          className={alreadyAdded ? "opacity-50" : ""}
                        />
                        {isDocument ? (
                          <FileText className="h-4 w-4 shrink-0 text-muted-foreground" />
                        ) : (
                          <VideoIcon className="h-4 w-4 shrink-0 text-muted-foreground" />
                        )}
                        <div className="min-w-0 flex-1">
                          <p className={`text-sm font-medium ${alreadyAdded ? "text-muted-foreground" : "text-foreground"}`}>
                            {item.title}
                          </p>
                          <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                            {isDocument ? (
                              <>
                                <Badge variant="outline" className={cn("text-[10px]", getContentTypeBadgeClass(item.contentType))}>
                                  {getContentTypeLabel(item.contentType)}
                                </Badge>
                                {item.page_count != null && (
                                  <span>{item.page_count} page{item.page_count !== 1 ? "s" : ""}</span>
                                )}
                                {item.file_size_bytes != null && (
                                  <span>{formatFileSize(item.file_size_bytes)}</span>
                                )}
                              </>
                            ) : (
                              <span>{formatDuration(item.duration_seconds)}</span>
                            )}
                          </div>
                        </div>
                      </div>
                      {alreadyAdded && (
                        <Badge variant="outline" className="shrink-0 whitespace-nowrap border-green-300 bg-green-100 text-xs text-green-700">
                          Added
                        </Badge>
                      )}
                    </div>
                    {item.tags.length > 0 && (
                      <div className="mt-3 flex flex-wrap gap-2 pl-7">
                        {item.tags.map((tag) => (
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
              ? "Select content to add to the collection."
              : `${selectedCount} item${selectedCount === 1 ? "" : "s"} ready to add.`}
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
                : `Add ${selectedCount} item${selectedCount === 1 ? "" : "s"}`}
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
