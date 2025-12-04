"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Folder, Trash2, Edit, MessageSquare, Video as VideoIcon } from "lucide-react";
import {
  getCollections,
  deleteCollection,
  getCollection,
} from "@/lib/api/collections";
import type { Collection } from "@/lib/types";
import { MainLayout } from "@/components/layout/MainLayout";
import { CollectionModal } from "@/components/collections/CollectionModal";

export default function CollectionsPage() {
  const queryClient = useQueryClient();
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [editingCollection, setEditingCollection] = useState<Collection | null>(null);
  const [expandedCollectionId, setExpandedCollectionId] = useState<string | null>(null);

  // Fetch collections
  const { data, isLoading, error } = useQuery({
    queryKey: ["collections"],
    queryFn: getCollections,
  });

  // Delete collection mutation
  const deleteMutation = useMutation({
    mutationFn: deleteCollection,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["collections"] });
    },
  });

  // Fetch expanded collection details
  const { data: expandedCollection } = useQuery({
    queryKey: ["collection", expandedCollectionId],
    queryFn: () => getCollection(expandedCollectionId!),
    enabled: !!expandedCollectionId,
  });

  const handleDelete = async (id: string, name: string, isDefault: boolean) => {
    if (isDefault) {
      alert("Cannot delete the default 'Uncategorized' collection");
      return;
    }

    if (confirm(`Are you sure you want to delete the collection "${name}"? Videos will not be deleted.`)) {
      try {
        await deleteMutation.mutateAsync(id);
      } catch (error) {
        console.error("Failed to delete collection:", error);
        alert("Failed to delete collection. Please try again.");
      }
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

  if (isLoading) {
    return (
      <MainLayout>
        <div className="flex items-center justify-center h-64">
          <div className="text-gray-500">Loading collections...</div>
        </div>
      </MainLayout>
    );
  }

  if (error) {
    return (
      <MainLayout>
        <div className="flex items-center justify-center h-64">
          <div className="text-red-500">Error loading collections: {(error as Error).message}</div>
        </div>
      </MainLayout>
    );
  }

  return (
    <MainLayout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Collections</h1>
            <p className="text-gray-600 mt-1">
              Organize your videos into collections by course, instructor, or topic
            </p>
          </div>
          <button
            onClick={() => setShowCreateModal(true)}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            <Plus className="w-5 h-5" />
            New Collection
          </button>
        </div>

        {/* Collections List */}
        {data && data.collections.length === 0 ? (
          <div className="text-center py-12 bg-gray-50 rounded-lg border-2 border-dashed border-gray-300">
            <Folder className="w-12 h-12 text-gray-400 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900 mb-2">No collections yet</h3>
            <p className="text-gray-600 mb-4">
              Create your first collection to organize your videos
            </p>
            <button
              onClick={() => setShowCreateModal(true)}
              className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
            >
              <Plus className="w-5 h-5" />
              Create Collection
            </button>
          </div>
        ) : (
          <div className="space-y-4">
            {data?.collections.map((collection) => {
              const isExpanded = expandedCollectionId === collection.id;
              const collectionDetails = isExpanded ? expandedCollection : null;

              return (
                <div
                  key={collection.id}
                  className="bg-white rounded-lg border border-gray-200 hover:border-gray-300 transition-colors"
                >
                  {/* Collection Header */}
                  <div className="p-6">
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-center gap-3">
                          <Folder
                            className={`w-6 h-6 ${
                              collection.is_default ? "text-gray-400" : "text-blue-600"
                            }`}
                          />
                          <div>
                            <h3 className="text-xl font-semibold text-gray-900">
                              {collection.name}
                              {collection.is_default && (
                                <span className="ml-2 text-sm font-normal text-gray-500">
                                  (Default)
                                </span>
                              )}
                            </h3>
                            {collection.description && (
                              <p className="text-gray-600 mt-1">{collection.description}</p>
                            )}
                          </div>
                        </div>

                        {/* Metadata */}
                        {collection.metadata && Object.keys(collection.metadata).length > 0 && (
                          <div className="mt-3 flex flex-wrap gap-2 ml-9">
                            {collection.metadata.instructor && (
                              <span className="px-2 py-1 bg-purple-100 text-purple-700 text-sm rounded">
                                👨‍🏫 {collection.metadata.instructor}
                              </span>
                            )}
                            {collection.metadata.subject && (
                              <span className="px-2 py-1 bg-green-100 text-green-700 text-sm rounded">
                                📚 {collection.metadata.subject}
                              </span>
                            )}
                            {collection.metadata.semester && (
                              <span className="px-2 py-1 bg-orange-100 text-orange-700 text-sm rounded">
                                📅 {collection.metadata.semester}
                              </span>
                            )}
                            {collection.metadata.tags?.map((tag: string) => (
                              <span
                                key={tag}
                                className="px-2 py-1 bg-gray-100 text-gray-700 text-sm rounded"
                              >
                                #{tag}
                              </span>
                            ))}
                          </div>
                        )}

                        {/* Stats */}
                        <div className="mt-3 flex items-center gap-4 text-sm text-gray-600 ml-9">
                          <span className="flex items-center gap-1">
                            <VideoIcon className="w-4 h-4" />
                            {collection.video_count} {collection.video_count === 1 ? "video" : "videos"}
                          </span>
                          {collection.total_duration_seconds > 0 && (
                            <span>• {formatDuration(collection.total_duration_seconds)} total</span>
                          )}
                        </div>
                      </div>

                      {/* Actions */}
                      <div className="flex items-center gap-2 ml-4">
                        <button
                          onClick={() => handleToggleExpand(collection.id)}
                          className="px-3 py-1 text-sm text-gray-700 bg-gray-100 rounded hover:bg-gray-200 transition-colors"
                        >
                          {isExpanded ? "Collapse" : "Expand"}
                        </button>
                        {!collection.is_default && (
                          <>
                            <button
                              onClick={() => setEditingCollection(collection)}
                              className="p-2 text-gray-600 hover:text-blue-600 hover:bg-blue-50 rounded transition-colors"
                              title="Edit collection"
                            >
                              <Edit className="w-5 h-5" />
                            </button>
                            <button
                              onClick={() => handleDelete(collection.id, collection.name, collection.is_default)}
                              className="p-2 text-gray-600 hover:text-red-600 hover:bg-red-50 rounded transition-colors"
                              title="Delete collection"
                            >
                              <Trash2 className="w-5 h-5" />
                            </button>
                          </>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Expanded Videos List */}
                  {isExpanded && collectionDetails && (
                    <div className="border-t border-gray-200 bg-gray-50 p-6">
                      {collectionDetails.videos.length === 0 ? (
                        <p className="text-gray-500 text-center py-4">No videos in this collection</p>
                      ) : (
                        <div className="space-y-2">
                          <h4 className="font-medium text-gray-900 mb-3">Videos in this collection:</h4>
                          {collectionDetails.videos.map((video) => (
                            <div
                              key={video.id}
                              className="flex items-center justify-between p-3 bg-white rounded border border-gray-200"
                            >
                              <div className="flex items-center gap-3 flex-1">
                                {video.thumbnail_url && (
                                  <img
                                    src={video.thumbnail_url}
                                    alt={video.title}
                                    className="w-20 h-12 object-cover rounded"
                                  />
                                )}
                                <div className="flex-1 min-w-0">
                                  <h5 className="font-medium text-gray-900 truncate">{video.title}</h5>
                                  <div className="flex items-center gap-2 text-sm text-gray-600 mt-1">
                                    {video.duration_seconds && (
                                      <span>{formatDuration(video.duration_seconds)}</span>
                                    )}
                                    <span className="capitalize">• {video.status}</span>
                                    {video.tags && video.tags.length > 0 && (
                                      <span className="flex gap-1 ml-2">
                                        {video.tags.map((tag) => (
                                          <span key={tag} className="px-1.5 py-0.5 bg-gray-100 text-xs rounded">
                                            #{tag}
                                          </span>
                                        ))}
                                      </span>
                                    )}
                                  </div>
                                </div>
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Create/Edit Modal */}
      {(showCreateModal || editingCollection) && (
        <CollectionModal
          collection={editingCollection}
          onClose={() => {
            setShowCreateModal(false);
            setEditingCollection(null);
          }}
        />
      )}
    </MainLayout>
  );
}
