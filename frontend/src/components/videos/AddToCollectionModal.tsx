"use client";

import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { X, Check, Folder, Plus, Minus } from "lucide-react";
import { getCollections, addVideosToCollection, removeVideoFromCollection } from "@/lib/api/collections";
import { videosApi } from "@/lib/api/videos";

interface AddToCollectionModalProps {
  videoIds: string[];
  videoTitle?: string;
  onClose: () => void;
}

interface ActionLogEntry {
  id: string;
  action: "added" | "removed";
  collectionName: string;
  timestamp: number;
}

export function AddToCollectionModal({
  videoIds,
  videoTitle,
  onClose,
}: AddToCollectionModalProps) {
  const queryClient = useQueryClient();
  const [error, setError] = useState<string>("");
  const [videoCollections, setVideoCollections] = useState<Set<string>>(new Set());
  const [actionLog, setActionLog] = useState<ActionLogEntry[]>([]);
  const videoCount = videoIds.length;
  const isSingleVideo = videoCount === 1;

  // Fetch collections
  const { data: collectionsData, isLoading } = useQuery({
    queryKey: ["collections"],
    queryFn: getCollections,
  });

  // Fetch which collections the video is already in (only for single video)
  useEffect(() => {
    if (isSingleVideo && videoIds[0]) {
      videosApi.getCollections(videoIds[0]).then((data) => {
        setVideoCollections(new Set(data.collection_ids));
      }).catch((err) => {
        console.error("Failed to fetch video collections:", err);
      });
    }
  }, [isSingleVideo, videoIds]);

  // Add video to collection mutation
  const addMutation = useMutation({
    mutationFn: ({ collectionId, videoIds }: { collectionId: string; videoIds: string[] }) =>
      addVideosToCollection(collectionId, { video_ids: videoIds }),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ["collections"] });
      queryClient.invalidateQueries({ queryKey: ["videos"] });
      setError("");

      // Update local state
      if (isSingleVideo) {
        setVideoCollections(prev => new Set(prev).add(variables.collectionId));
      }

      // Add to action log
      const collectionName =
        collectionsData?.collections.find((collection) => collection.id === variables.collectionId)
          ?.name ?? "collection";

      setActionLog(prev => [
        {
          id: `${variables.collectionId}-${Date.now()}`,
          action: "added",
          collectionName,
          timestamp: Date.now(),
        },
        ...prev,
      ]);
    },
    onError: (error: any, variables) => {
      const collectionName =
        collectionsData?.collections.find((collection) => collection.id === variables.collectionId)
          ?.name ?? "collection";
      setError(`Failed to add to ${collectionName}: ${error.response?.data?.detail || "Unknown error"}`);
    },
  });

  // Remove video from collection mutation
  const removeMutation = useMutation({
    mutationFn: ({ collectionId, videoId }: { collectionId: string; videoId: string }) =>
      removeVideoFromCollection(collectionId, videoId),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ["collections"] });
      queryClient.invalidateQueries({ queryKey: ["videos"] });
      setError("");

      // Update local state
      if (isSingleVideo) {
        setVideoCollections(prev => {
          const newSet = new Set(prev);
          newSet.delete(variables.collectionId);
          return newSet;
        });
      }

      // Add to action log
      const collectionName =
        collectionsData?.collections.find((collection) => collection.id === variables.collectionId)
          ?.name ?? "collection";

      setActionLog(prev => [
        {
          id: `${variables.collectionId}-${Date.now()}`,
          action: "removed",
          collectionName,
          timestamp: Date.now(),
        },
        ...prev,
      ]);
    },
    onError: (error: any, variables) => {
      const collectionName =
        collectionsData?.collections.find((collection) => collection.id === variables.collectionId)
          ?.name ?? "collection";
      setError(`Failed to remove from ${collectionName}: ${error.response?.data?.detail || "Unknown error"}`);
    },
  });

  const handleCheckboxChange = async (collectionId: string, isChecked: boolean) => {
    setError("");

    if (isChecked) {
      // Add to collection
      await addMutation.mutateAsync({
        collectionId,
        videoIds,
      });
    } else {
      // Remove from collection (single video only)
      if (isSingleVideo) {
        await removeMutation.mutateAsync({
          collectionId,
          videoId: videoIds[0],
        });
      }
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-lg shadow-xl max-w-md w-full">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200">
          <h2 className="text-xl font-bold text-gray-900">Manage Collections</h2>
          <button
            onClick={onClose}
            className="p-2 text-gray-400 hover:text-gray-600 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6">
          {/* Action Log - Show only most recent action */}
          {actionLog.length > 0 && (
            <div className="mb-4">
              {(() => {
                const latestEntry = actionLog[0];
                return (
                  <div
                    key={latestEntry.id}
                    className="flex items-center gap-2 text-sm px-3 py-2 bg-gray-50 rounded-lg"
                  >
                    {latestEntry.action === "added" ? (
                      <Plus className="w-4 h-4 text-green-600 flex-shrink-0" />
                    ) : (
                      <Minus className="w-4 h-4 text-red-600 flex-shrink-0" />
                    )}
                    <span className="text-gray-900">
                      {latestEntry.action === "added" ? "Added to" : "Removed from"}{" "}
                      <span className="font-medium">{latestEntry.collectionName}</span>
                    </span>
                  </div>
                );
              })()}
            </div>
          )}

          <div className="mb-4">
            <p className="text-sm text-gray-600 mb-4">
              {videoCount === 1 && videoTitle ? (
                <>
                  Manage collections for{" "}
                  <span className="font-medium text-gray-900">
                    &ldquo;{videoTitle}&rdquo;
                  </span>
                </>
              ) : (
                <>
                  Manage collections for{" "}
                  <span className="font-medium text-gray-900">
                    {videoCount} video{videoCount !== 1 ? "s" : ""}
                  </span>
                </>
              )}
            </p>

            {isLoading ? (
              <div className="text-center py-4">
                <div className="text-gray-500">Loading collections...</div>
              </div>
            ) : collectionsData && collectionsData.collections.length > 0 ? (
              <div className="space-y-2 max-h-64 overflow-y-auto">
                {collectionsData.collections.map((collection) => {
                  const isInCollection = isSingleVideo && videoCollections.has(collection.id);
                  const isDisabled = addMutation.isPending || removeMutation.isPending;

                  return (
                    <label
                      key={collection.id}
                      className={`flex items-center p-3 border rounded-lg cursor-pointer transition-colors ${
                        isDisabled
                          ? "opacity-50 cursor-not-allowed"
                          : "hover:border-gray-400"
                      } border-gray-200`}
                    >
                      <input
                        type="checkbox"
                        checked={isInCollection}
                        disabled={isDisabled}
                        onChange={(e) => handleCheckboxChange(collection.id, e.target.checked)}
                        className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                      />
                      <Folder
                        className={`w-5 h-5 mx-3 ${
                          collection.is_default ? "text-gray-400" : "text-blue-600"
                        }`}
                      />
                      <div className="flex-1">
                        <div className="font-medium text-gray-900">{collection.name}</div>
                        {collection.description && (
                          <div className="text-sm text-gray-500">{collection.description}</div>
                        )}
                        <div className="text-xs text-gray-500 mt-1">
                          {collection.video_count} videos
                        </div>
                      </div>
                    </label>
                  );
                })}
              </div>
            ) : (
              <div className="text-center py-4 text-gray-500">
                No collections available. Create one first.
              </div>
            )}
          </div>

          {error && (
            <div className="mt-4 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
              {error}
            </div>
          )}

          {/* Actions */}
          <div className="flex justify-end pt-4 border-t border-gray-200 mt-4">
            <button
              type="button"
              onClick={onClose}
              className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
              disabled={addMutation.isPending || removeMutation.isPending}
            >
              Done
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
