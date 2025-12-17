"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { X, Check, Folder } from "lucide-react";
import { getCollections, addVideosToCollection } from "@/lib/api/collections";

interface AddToCollectionModalProps {
  videoIds: string[];
  videoTitle?: string;
  onClose: () => void;
}

export function AddToCollectionModal({
  videoIds,
  videoTitle,
  onClose,
}: AddToCollectionModalProps) {
  const queryClient = useQueryClient();
  const [selectedCollectionId, setSelectedCollectionId] = useState<string>("");
  const [error, setError] = useState<string>("");
  const [success, setSuccess] = useState<string>("");
  const videoCount = videoIds.length;

  // Fetch collections
  const { data: collectionsData, isLoading } = useQuery({
    queryKey: ["collections"],
    queryFn: getCollections,
  });

  // Add video to collection mutation
  const addMutation = useMutation({
    mutationFn: ({ collectionId, videoIds }: { collectionId: string; videoIds: string[] }) =>
      addVideosToCollection(collectionId, { video_ids: videoIds }),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ["collections"] });
      queryClient.invalidateQueries({ queryKey: ["videos"] });
      setError("");

      const collectionName =
        collectionsData?.collections.find((collection) => collection.id === variables.collectionId)
          ?.name ?? "collection";
      const videoLabel =
        videoCount === 1 && videoTitle
          ? `"${videoTitle}"`
          : `${videoCount} video${videoCount === 1 ? "" : "s"}`;
      setSuccess(`Added ${videoLabel} to ${collectionName}`);
    },
    onError: (error: any) => {
      setSuccess("");
      setError(error.response?.data?.detail || "Failed to add video to collection");
    },
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setSuccess("");

    if (!selectedCollectionId) {
      setError("Please select a collection");
      return;
    }

    await addMutation.mutateAsync({
      collectionId: selectedCollectionId,
      videoIds,
    });
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-lg shadow-xl max-w-md w-full">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200">
          <h2 className="text-xl font-bold text-gray-900">Add to Collection</h2>
          <button
            onClick={onClose}
            className="p-2 text-gray-400 hover:text-gray-600 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <form onSubmit={handleSubmit} className="p-6">
          <div className="mb-4">
            <p className="text-sm text-gray-600 mb-4">
              {videoCount === 1 && videoTitle ? (
                <>
                  Add{" "}
                  <span className="font-medium text-gray-900">
                    &ldquo;{videoTitle}&rdquo;
                  </span>{" "}
                  to:
                </>
              ) : (
                <>
                  Add{" "}
                  <span className="font-medium text-gray-900">
                    {videoCount} video{videoCount !== 1 ? "s" : ""}
                  </span>{" "}
                  to:
                </>
              )}
            </p>

            {isLoading ? (
              <div className="text-center py-4">
                <div className="text-gray-500">Loading collections...</div>
              </div>
            ) : collectionsData && collectionsData.collections.length > 0 ? (
              <div className="space-y-2 max-h-64 overflow-y-auto">
                {collectionsData.collections.map((collection) => (
                  <label
                    key={collection.id}
                    className={`flex items-center p-3 border rounded-lg cursor-pointer transition-colors ${
                      selectedCollectionId === collection.id
                        ? "border-blue-500 bg-blue-50"
                        : "border-gray-200 hover:border-gray-300"
                    }`}
                  >
                    <input
                      type="radio"
                      name="collection"
                      value={collection.id}
                      checked={selectedCollectionId === collection.id}
                      onChange={(e) => {
                        setSelectedCollectionId(e.target.value);
                        setSuccess("");
                        setError("");
                      }}
                      className="sr-only"
                    />
                    <Folder
                      className={`w-5 h-5 mr-3 ${
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
                    {selectedCollectionId === collection.id && (
                      <Check className="w-5 h-5 text-blue-600" />
                    )}
                  </label>
                ))}
              </div>
            ) : (
              <div className="text-center py-4 text-gray-500">
                No collections available. Create one first.
              </div>
            )}
          </div>

          {error && (
            <div className="mb-4 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
              {error}
            </div>
          )}

          {success && (
            <div className="mb-4 flex items-center gap-2 rounded border border-emerald-200 bg-emerald-50 px-4 py-3 text-emerald-800">
              <Check className="h-4 w-4 text-emerald-700" />
              <p className="text-sm font-medium">{success}</p>
            </div>
          )}

          {/* Actions */}
          <div className="flex justify-end gap-3 pt-4 border-t border-gray-200">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors"
              disabled={addMutation.isPending}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              disabled={addMutation.isPending || !selectedCollectionId}
            >
              {addMutation.isPending ? "Adding..." : "Add to Collection"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
