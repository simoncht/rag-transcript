"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { MainLayout } from "@/components/layout/MainLayout";
import { videosApi } from "@/lib/api/videos";
import { Video } from "@/lib/types";
import { Plus, Trash2, ExternalLink, Loader2 } from "lucide-react";
import { formatDistanceToNow } from "date-fns";

export default function VideosPage() {
  const [youtubeUrl, setYoutubeUrl] = useState("");
  const [showAddForm, setShowAddForm] = useState(false);
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ["videos"],
    queryFn: () => videosApi.list(),
  });

  const ingestMutation = useMutation({
    mutationFn: videosApi.ingest,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["videos"] });
      setYoutubeUrl("");
      setShowAddForm(false);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: videosApi.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["videos"] });
    },
  });

  const handleIngest = (e: React.FormEvent) => {
    e.preventDefault();
    if (youtubeUrl.trim()) {
      ingestMutation.mutate(youtubeUrl.trim());
    }
  };

  const getStatusColor = (status: Video["status"]) => {
    switch (status) {
      case "completed":
        return "bg-green-100 text-green-800";
      case "processing":
        return "bg-blue-100 text-blue-800";
      case "failed":
        return "bg-red-100 text-red-800";
      default:
        return "bg-gray-100 text-gray-800";
    }
  };

  const formatDuration = (seconds: number) => {
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${minutes}:${remainingSeconds.toString().padStart(2, "0")}`;
  };

  return (
    <MainLayout>
      <div className="px-4 sm:px-0">
        <div className="sm:flex sm:items-center sm:justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Videos</h1>
            <p className="mt-1 text-sm text-gray-500">
              Manage your YouTube video transcripts
            </p>
          </div>
          <button
            onClick={() => setShowAddForm(!showAddForm)}
            className="mt-4 sm:mt-0 inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
          >
            <Plus className="w-4 h-4 mr-2" />
            Add Video
          </button>
        </div>

        {showAddForm && (
          <div className="bg-white shadow sm:rounded-lg mb-6">
            <form onSubmit={handleIngest} className="p-6">
              <div className="mb-4">
                <label
                  htmlFor="youtube-url"
                  className="block text-sm font-medium text-gray-700 mb-2"
                >
                  YouTube URL
                </label>
                <input
                  type="url"
                  id="youtube-url"
                  value={youtubeUrl}
                  onChange={(e) => setYoutubeUrl(e.target.value)}
                  placeholder="https://www.youtube.com/watch?v=..."
                  className="block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
                  required
                />
              </div>
              <div className="flex justify-end space-x-3">
                <button
                  type="button"
                  onClick={() => {
                    setShowAddForm(false);
                    setYoutubeUrl("");
                  }}
                  className="px-4 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={ingestMutation.isPending}
                  className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {ingestMutation.isPending && (
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  )}
                  Ingest Video
                </button>
              </div>
            </form>
          </div>
        )}

        {isLoading ? (
          <div className="flex justify-center items-center py-12">
            <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
          </div>
        ) : (
          <div className="bg-white shadow overflow-hidden sm:rounded-md">
            {data?.videos.length === 0 ? (
              <div className="text-center py-12">
                <p className="text-gray-500">No videos yet. Add your first video to get started.</p>
              </div>
            ) : (
              <ul className="divide-y divide-gray-200">
                {data?.videos.map((video) => (
                  <li key={video.id} className="px-6 py-4 hover:bg-gray-50">
                    <div className="flex items-center justify-between">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center space-x-3">
                          <h3 className="text-sm font-medium text-gray-900 truncate">
                            {video.title}
                          </h3>
                          <span
                            className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getStatusColor(
                              video.status
                            )}`}
                          >
                            {video.status}
                          </span>
                        </div>
                        <div className="mt-2 flex items-center space-x-4 text-sm text-gray-500">
                          <span>{formatDuration(video.duration_seconds)}</span>
                          <span>•</span>
                          <span>
                            Added {formatDistanceToNow(new Date(video.created_at))} ago
                          </span>
                          <a
                            href={video.youtube_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center text-blue-600 hover:text-blue-800"
                          >
                            <ExternalLink className="w-4 h-4 mr-1" />
                            View on YouTube
                          </a>
                        </div>
                        {video.error_message && (
                          <p className="mt-2 text-sm text-red-600">
                            {video.error_message}
                          </p>
                        )}
                      </div>
                      <div className="ml-4">
                        <button
                          onClick={() => deleteMutation.mutate(video.id)}
                          disabled={deleteMutation.isPending}
                          className="p-2 text-gray-400 hover:text-red-600 focus:outline-none"
                        >
                          <Trash2 className="w-5 h-5" />
                        </button>
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>
    </MainLayout>
  );
}
