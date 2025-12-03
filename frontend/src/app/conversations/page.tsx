"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { MainLayout } from "@/components/layout/MainLayout";
import { conversationsApi } from "@/lib/api/conversations";
import { videosApi } from "@/lib/api/videos";
import { Plus, Trash2, MessageSquare, Loader2 } from "lucide-react";
import { formatDistanceToNow } from "date-fns";

export default function ConversationsPage() {
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [title, setTitle] = useState("");
  const [selectedVideoIds, setSelectedVideoIds] = useState<string[]>([]);
  const queryClient = useQueryClient();
  const router = useRouter();

  const { data: conversationsData, isLoading: conversationsLoading } = useQuery({
    queryKey: ["conversations"],
    queryFn: () => conversationsApi.list(),
  });

  const { data: videosData } = useQuery({
    queryKey: ["videos"],
    queryFn: () => videosApi.list(),
    enabled: showCreateForm,
  });

  const createMutation = useMutation({
    mutationFn: ({ title, videoIds }: { title: string; videoIds: string[] }) =>
      conversationsApi.create(title, videoIds),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["conversations"] });
      setTitle("");
      setSelectedVideoIds([]);
      setShowCreateForm(false);
      router.push(`/conversations/${data.id}`);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: conversationsApi.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["conversations"] });
    },
  });

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault();
    if (selectedVideoIds.length > 0) {
      createMutation.mutate({ title, videoIds: selectedVideoIds });
    }
  };

  const toggleVideoSelection = (videoId: string) => {
    setSelectedVideoIds((prev) =>
      prev.includes(videoId)
        ? prev.filter((id) => id !== videoId)
        : [...prev, videoId]
    );
  };

  const completedVideos = videosData?.videos.filter(
    (v) => v.status === "completed"
  );

  return (
    <MainLayout>
      <div className="px-4 sm:px-0">
        <div className="sm:flex sm:items-center sm:justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Conversations</h1>
            <p className="mt-1 text-sm text-gray-500">
              Chat with your video transcripts
            </p>
          </div>
          <button
            onClick={() => setShowCreateForm(!showCreateForm)}
            className="mt-4 sm:mt-0 inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
          >
            <Plus className="w-4 h-4 mr-2" />
            New Conversation
          </button>
        </div>

        {showCreateForm && (
          <div className="bg-white shadow sm:rounded-lg mb-6">
            <form onSubmit={handleCreate} className="p-6">
              <div className="mb-4">
                <label
                  htmlFor="title"
                  className="block text-sm font-medium text-gray-700 mb-2"
                >
                  Title (optional)
                </label>
                <input
                  type="text"
                  id="title"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="Auto-generated if left blank"
                  className="block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
                />
              </div>
              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Select Videos
                </label>
                <div className="max-h-48 overflow-y-auto border border-gray-300 rounded-md">
                  {completedVideos?.length === 0 ? (
                    <p className="p-4 text-sm text-gray-500">
                      No completed videos available. Please ingest videos first.
                    </p>
                  ) : (
                    <div className="divide-y divide-gray-200">
                      {completedVideos?.map((video) => (
                        <label
                          key={video.id}
                          className="flex items-center p-3 hover:bg-gray-50 cursor-pointer"
                        >
                          <input
                            type="checkbox"
                            checked={selectedVideoIds.includes(video.id)}
                            onChange={() => toggleVideoSelection(video.id)}
                            className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                          />
                          <span className="ml-3 text-sm text-gray-900">
                            {video.title}
                          </span>
                        </label>
                      ))}
                    </div>
                  )}
                </div>
              </div>
              <div className="flex justify-end space-x-3">
                <button
                  type="button"
                  onClick={() => {
                    setShowCreateForm(false);
                    setTitle("");
                    setSelectedVideoIds([]);
                  }}
                  className="px-4 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={
                    selectedVideoIds.length === 0 || createMutation.isPending
                  }
                  className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {createMutation.isPending && (
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  )}
                  Create Conversation
                </button>
              </div>
            </form>
          </div>
        )}

        {conversationsLoading ? (
          <div className="flex justify-center items-center py-12">
            <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
          </div>
        ) : (
          <div className="bg-white shadow overflow-hidden sm:rounded-md">
            {conversationsData?.conversations.length === 0 ? (
              <div className="text-center py-12">
                <MessageSquare className="mx-auto h-12 w-12 text-gray-400" />
                <h3 className="mt-2 text-sm font-medium text-gray-900">
                  No conversations
                </h3>
                <p className="mt-1 text-sm text-gray-500">
                  Get started by creating a new conversation.
                </p>
              </div>
            ) : (
              <ul className="divide-y divide-gray-200">
                {conversationsData?.conversations.map((conversation) => (
                  <li key={conversation.id} className="hover:bg-gray-50">
                    <div className="px-6 py-4 flex items-center justify-between">
                      <div
                        className="flex-1 cursor-pointer"
                        onClick={() =>
                          router.push(`/conversations/${conversation.id}`)
                        }
                      >
                        <h3 className="text-sm font-medium text-gray-900">
                          {conversation.title}
                        </h3>
                        <div className="mt-2 flex items-center space-x-4 text-sm text-gray-500">
                          <span>
                            {conversation.message_count} message
                            {conversation.message_count !== 1 ? "s" : ""}
                          </span>
                          <span>•</span>
                          <span>
                            {conversation.selected_video_ids.length} video
                            {conversation.selected_video_ids.length !== 1 ? "s" : ""}
                          </span>
                          <span>•</span>
                          <span>
                            {conversation.last_message_at
                              ? `Active ${formatDistanceToNow(
                                  new Date(conversation.last_message_at)
                                )} ago`
                              : `Created ${formatDistanceToNow(
                                  new Date(conversation.created_at)
                                )} ago`}
                          </span>
                        </div>
                      </div>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          deleteMutation.mutate(conversation.id);
                        }}
                        disabled={deleteMutation.isPending}
                        className="ml-4 p-2 text-gray-400 hover:text-red-600 focus:outline-none"
                      >
                        <Trash2 className="w-5 h-5" />
                      </button>
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
