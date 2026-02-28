"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { X, Tag, Plus, Loader2 } from "lucide-react";
import { videosApi } from "@/lib/api/videos";
import { useAuth, createParallelQueryFn } from "@/lib/auth";
import { VideoFilterValues } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

interface BulkTagModalProps {
  videoIds: string[];
  onClose: () => void;
}

export function BulkTagModal({ videoIds, onClose }: BulkTagModalProps) {
  const queryClient = useQueryClient();
  const authProvider = useAuth();
  const [addTags, setAddTags] = useState<string[]>([]);
  const [removeTags, setRemoveTags] = useState<string[]>([]);
  const [newTag, setNewTag] = useState("");
  const [error, setError] = useState("");

  const { data: filterValues } = useQuery<VideoFilterValues>({
    queryKey: ["video-filters"],
    queryFn: createParallelQueryFn(authProvider, () => videosApi.getFilters()),
    staleTime: 60_000,
  });

  const mutation = useMutation({
    mutationFn: () => videosApi.bulkUpdateTags(videoIds, addTags, removeTags),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["videos"] });
      queryClient.invalidateQueries({ queryKey: ["video-filters"] });
      onClose();
    },
    onError: (err: any) => {
      setError(err.response?.data?.detail || "Failed to update tags");
    },
  });

  const handleAddNewTag = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = newTag.trim();
    if (trimmed && !addTags.includes(trimmed)) {
      setAddTags([...addTags, trimmed]);
      // If it was in remove list, take it out
      setRemoveTags(removeTags.filter((t) => t !== trimmed));
      setNewTag("");
    }
  };

  const toggleExistingTag = (tag: string) => {
    if (addTags.includes(tag)) {
      setAddTags(addTags.filter((t) => t !== tag));
    } else if (removeTags.includes(tag)) {
      setRemoveTags(removeTags.filter((t) => t !== tag));
    } else {
      // By default clicking an existing tag adds it
      setAddTags([...addTags, tag]);
    }
  };

  const markForRemoval = (tag: string) => {
    if (removeTags.includes(tag)) {
      setRemoveTags(removeTags.filter((t) => t !== tag));
    } else {
      setRemoveTags([...removeTags, tag]);
      setAddTags(addTags.filter((t) => t !== tag));
    }
  };

  const existingTags = filterValues?.tags.map((t) => t.name) ?? [];
  const hasChanges = addTags.length > 0 || removeTags.length > 0;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
      <div className="bg-background border rounded-lg shadow-xl max-w-md w-full">
        <div className="flex items-center justify-between p-4 border-b">
          <h2 className="text-lg font-semibold">
            Tag {videoIds.length} video{videoIds.length !== 1 ? "s" : ""}
          </h2>
          <button
            onClick={onClose}
            className="p-1.5 text-muted-foreground hover:text-foreground rounded-md"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="p-4 space-y-4">
          {/* Add new tag */}
          <div>
            <label className="text-xs font-medium text-muted-foreground mb-1.5 block">
              Add new tag
            </label>
            <form onSubmit={handleAddNewTag} className="flex gap-2">
              <Input
                value={newTag}
                onChange={(e) => setNewTag(e.target.value)}
                placeholder="Type a tag name..."
                className="flex-1"
              />
              <Button type="submit" variant="outline" size="icon" disabled={!newTag.trim()}>
                <Plus className="h-4 w-4" />
              </Button>
            </form>
          </div>

          {/* Tags to add */}
          {addTags.length > 0 && (
            <div>
              <label className="text-xs font-medium text-emerald-600 mb-1.5 block">
                Adding
              </label>
              <div className="flex flex-wrap gap-1.5">
                {addTags.map((tag) => (
                  <Badge
                    key={tag}
                    className="gap-1 pl-2 pr-1 text-xs bg-emerald-50 text-emerald-700 border-emerald-200 cursor-pointer"
                    variant="outline"
                    onClick={() => setAddTags(addTags.filter((t) => t !== tag))}
                  >
                    <Tag className="h-3 w-3" />
                    {tag}
                    <X className="h-3 w-3 ml-0.5" />
                  </Badge>
                ))}
              </div>
            </div>
          )}

          {/* Tags to remove */}
          {removeTags.length > 0 && (
            <div>
              <label className="text-xs font-medium text-destructive mb-1.5 block">
                Removing
              </label>
              <div className="flex flex-wrap gap-1.5">
                {removeTags.map((tag) => (
                  <Badge
                    key={tag}
                    className="gap-1 pl-2 pr-1 text-xs bg-destructive/10 text-destructive border-destructive/30 cursor-pointer line-through"
                    variant="outline"
                    onClick={() => setRemoveTags(removeTags.filter((t) => t !== tag))}
                  >
                    <Tag className="h-3 w-3" />
                    {tag}
                    <X className="h-3 w-3 ml-0.5" />
                  </Badge>
                ))}
              </div>
            </div>
          )}

          {/* Existing tags quick-pick */}
          {existingTags.length > 0 && (
            <div>
              <label className="text-xs font-medium text-muted-foreground mb-1.5 block">
                Existing tags (click to add, right-click to remove)
              </label>
              <div className="flex flex-wrap gap-1.5">
                {existingTags
                  .filter((t) => !addTags.includes(t) && !removeTags.includes(t))
                  .map((tag) => (
                    <Badge
                      key={tag}
                      variant="outline"
                      className="text-xs cursor-pointer hover:bg-accent"
                      onClick={() => toggleExistingTag(tag)}
                      onContextMenu={(e) => {
                        e.preventDefault();
                        markForRemoval(tag);
                      }}
                    >
                      <Tag className="h-3 w-3 mr-1" />
                      {tag}
                    </Badge>
                  ))}
              </div>
            </div>
          )}

          {error && (
            <p className="text-sm text-destructive">{error}</p>
          )}
        </div>

        <div className="flex justify-end gap-2 p-4 border-t">
          <Button variant="outline" size="sm" onClick={onClose} disabled={mutation.isPending}>
            Cancel
          </Button>
          <Button
            size="sm"
            onClick={() => mutation.mutate()}
            disabled={!hasChanges || mutation.isPending}
          >
            {mutation.isPending ? (
              <>
                <Loader2 className="h-3.5 w-3.5 animate-spin mr-1.5" />
                Applying...
              </>
            ) : (
              "Apply tags"
            )}
          </Button>
        </div>
      </div>
    </div>
  );
}
