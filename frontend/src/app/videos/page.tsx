"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { MainLayout } from "@/components/layout/MainLayout";
import { videosApi } from "@/lib/api/videos";
import { usageApi } from "@/lib/api/usage";
import { getCollections } from "@/lib/api/collections";
import { Video, VideoDeleteRequest } from "@/lib/types";
import { DeleteConfirmationModal } from "@/components/videos/DeleteConfirmationModal";
import {
  Plus,
  Trash2,
  ExternalLink,
  Loader2,
  FolderPlus,
  Tag as TagIcon,
  FileText,
  ChevronDown,
  ChevronUp,
  Copy,
  Download,
  Search,
} from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import { AddToCollectionModal } from "@/components/videos/AddToCollectionModal";
import { ManageTagsModal } from "@/components/videos/ManageTagsModal";

export default function VideosPage() {
  const [youtubeUrl, setYoutubeUrl] = useState("");
  const [showAddForm, setShowAddForm] = useState(false);
  const [addToCollectionVideo, setAddToCollectionVideo] = useState<Video | null>(null);
  const [manageTagsVideo, setManageTagsVideo] = useState<Video | null>(null);
  const [selectedVideoIds, setSelectedVideoIds] = useState<Set<string>>(new Set());
  const [openTranscriptVideoId, setOpenTranscriptVideoId] = useState<string | null>(null);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [videosToDelete, setVideosToDelete] = useState<Video[]>([]);
  const queryClient = useQueryClient();

  const { data: usageSummary } = useQuery({
    queryKey: ["usage-summary"],
    queryFn: () => usageApi.getSummary(),
    staleTime: 30_000,
  });

  const { data, isLoading } = useQuery({
    queryKey: ["videos"],
    queryFn: () => videosApi.list(),
    // Poll while any video is still processing
    refetchInterval: (query) => {
      const videos = query.state.data?.videos ?? [];
      const hasInFlight = videos.some(
        (video) => !["completed", "failed"].includes(video.status)
      );
      return hasInFlight ? 2000 : false;
    },
  });

  // Fetch collections to show which collections each video belongs to
  const { data: collectionsData } = useQuery({
    queryKey: ["collections"],
    queryFn: getCollections,
  });

  // Helper function to get collections for a video
  const getVideoCollections = (videoId: string) => {
    if (!collectionsData) return [];
    return collectionsData.collections.filter((collection) =>
      collection.video_count > 0 // We'll need to fetch full collection details to check membership
    );
  };

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
    onSuccess: (_data, videoId) => {
      setSelectedVideoIds((prev) => {
        const next = new Set(prev);
        if (videoId) {
          next.delete(videoId);
        }
        return next;
      });
      queryClient.invalidateQueries({ queryKey: ["videos"] });
    },
  });

  const bulkDeleteMutation = useMutation({
    mutationFn: async (request: VideoDeleteRequest) => {
      return videosApi.deleteMultiple(request);
    },
    onSuccess: () => {
      setSelectedVideoIds(new Set());
      setShowDeleteModal(false);
      setVideosToDelete([]);
      queryClient.invalidateQueries({ queryKey: ["videos"] });
      queryClient.invalidateQueries({ queryKey: ["usage-summary"] });
    },
    onError: (error) => {
      console.error("Delete failed:", error);
      alert("Failed to delete videos. Please try again.");
    },
  });

  const handleIngest = (e: React.FormEvent) => {
    e.preventDefault();
    if (youtubeUrl.trim()) {
      ingestMutation.mutate(youtubeUrl.trim());
    }
  };

  const isDeletable = (video: Video) => ["completed", "failed"].includes(video.status);

  const toggleSelection = (videoId: string, enabled: boolean) => {
    setSelectedVideoIds((prev) => {
      const next = new Set(prev);
      if (enabled) {
        next.add(videoId);
      } else {
        next.delete(videoId);
      }
      return next;
    });
  };

  const handleDelete = (video: Video) => {
    if (!isDeletable(video)) return;
    setVideosToDelete([video]);
    setShowDeleteModal(true);
  };

  const handleBulkDelete = () => {
    const ids = Array.from(selectedVideoIds);
    if (ids.length === 0) return;
    const videosToDelete = data?.videos.filter((v) => ids.includes(v.id)) || [];
    setVideosToDelete(videosToDelete);
    setShowDeleteModal(true);
  };

  const handleConfirmDelete = async (options: {
    removeFromLibrary: boolean;
    deleteSearchIndex: boolean;
    deleteAudio: boolean;
    deleteTranscript: boolean;
  }) => {
    const videoIds = videosToDelete.map((v) => v.id);
    const request: VideoDeleteRequest = {
      video_ids: videoIds,
      remove_from_library: options.removeFromLibrary,
      delete_search_index: options.deleteSearchIndex,
      delete_audio: options.deleteAudio,
      delete_transcript: options.deleteTranscript,
    };
    bulkDeleteMutation.mutate(request);
  };

  const getStatusColor = (status: Video["status"]) => {
    switch (status) {
      case "completed":
        return "bg-green-100 text-green-800";
      case "processing":
      case "pending":
      case "downloading":
      case "transcribing":
      case "chunking":
      case "enriching":
      case "indexing":
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

  const formatTimestamp = (seconds: number) => {
    const hrs = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    if (hrs > 0) {
      return `${hrs}:${mins.toString().padStart(2, "0")}:${secs
        .toString()
        .padStart(2, "0")}`;
    }
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  };

  const formatMb = (value?: number) => {
    if (value === undefined || value === null) return "0 MB";
    if (value > 0 && value < 0.1) return "<0.1 MB";
    return `${value.toFixed(1)} MB`;
  };

  const toggleTranscript = (videoId: string) => {
    setOpenTranscriptVideoId((prev) => (prev === videoId ? null : videoId));
  };

  const TranscriptPanel = ({ videoId, isOpen }: { videoId: string; isOpen: boolean }) => {
    const [activeTab, setActiveTab] = useState<"readable" | "timeline">("readable");
    const [search, setSearch] = useState("");
    const { data, isLoading, isError, refetch } = useQuery({
      queryKey: ["video-transcript", videoId],
      queryFn: () => videosApi.getTranscript(videoId),
      enabled: isOpen,
    });

    if (!isOpen) return null;

    const buildParagraphs = () => {
      if (!data) return [];
      const PARAGRAPH_BREAK_SECONDS = 8;
      const paragraphs: string[] = [];
      let current: string[] = [];

      data.segments.forEach((segment, idx) => {
        const text = segment.text.trim();
        if (!text) return;
        const prev = data.segments[idx - 1];
        const gap = prev ? segment.start - prev.end : 0;
        const speakerChanged =
          prev && prev.speaker && segment.speaker && prev.speaker !== segment.speaker;

        if (current.length > 0 && (gap > PARAGRAPH_BREAK_SECONDS || speakerChanged)) {
          paragraphs.push(current.join(" "));
          current = [];
        }
        current.push(text);
      });

      if (current.length > 0) {
        paragraphs.push(current.join(" "));
      }

      return paragraphs;
    };

    const paragraphs = buildParagraphs();
    const filteredSegments =
      data?.segments.filter((segment) =>
        search.trim()
          ? segment.text.toLowerCase().includes(search.toLowerCase()) ||
            (segment.speaker || "").toLowerCase().includes(search.toLowerCase())
          : true
      ) ?? [];

    const handleCopy = async () => {
      if (!data) return;
      try {
        await navigator.clipboard.writeText(data.full_text);
      } catch (err) {
        console.warn("Copy failed", err);
      }
    };

    const handleDownload = () => {
      if (!data) return;
      const blob = new Blob([data.full_text], { type: "text/plain" });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "transcript.txt";
      link.click();
      window.URL.revokeObjectURL(url);
    };

    return (
      <div className="mt-3 rounded-md border border-gray-200 bg-gray-50 p-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2 text-sm font-medium text-gray-800">
            <FileText className="w-4 h-4" />
            <span>Transcript</span>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={handleCopy}
              disabled={!data}
              className="inline-flex items-center rounded border border-gray-300 px-2 py-1 text-xs text-gray-700 hover:bg-white disabled:opacity-50"
            >
              <Copy className="mr-1 h-3.5 w-3.5" />
              Copy
            </button>
            <button
              onClick={handleDownload}
              disabled={!data}
              className="inline-flex items-center rounded border border-gray-300 px-2 py-1 text-xs text-gray-700 hover:bg-white disabled:opacity-50"
            >
              <Download className="mr-1 h-3.5 w-3.5" />
              Download
            </button>
            <button
              onClick={() => refetch()}
              className="text-xs text-blue-600 hover:text-blue-800"
              disabled={isLoading}
            >
              Refresh
            </button>
          </div>
        </div>

        {isLoading && (
          <div className="mt-3 flex items-center text-sm text-gray-600">
            <Loader2 className="w-4 h-4 mr-2 animate-spin" />
            Loading transcript...
          </div>
        )}

        {isError && (
          <div className="mt-3 text-sm text-red-600">
            Transcript not available yet. Try again after processing finishes.
          </div>
        )}

        {data && (
          <div className="mt-3 space-y-3">
            <div className="flex flex-wrap items-center gap-2 text-sm text-gray-700">
              {data.language && (
                <span className="inline-flex items-center rounded bg-white px-2 py-1 text-xs text-gray-700">
                  Language: {data.language}
                </span>
              )}
              <span className="inline-flex items-center rounded bg-white px-2 py-1 text-xs text-gray-700">
                Duration: {formatDuration(data.duration_seconds)}
              </span>
              <span className="inline-flex items-center rounded bg-white px-2 py-1 text-xs text-gray-700">
                Words: {data.word_count}
              </span>
            </div>

            <div className="flex items-center gap-2 text-xs font-medium text-gray-700">
              <button
                onClick={() => setActiveTab("readable")}
                className={`rounded px-3 py-1 ${
                  activeTab === "readable"
                    ? "bg-white text-gray-900 shadow-sm"
                    : "bg-gray-200 text-gray-700"
                }`}
              >
                Readable
              </button>
              <button
                onClick={() => setActiveTab("timeline")}
                className={`rounded px-3 py-1 ${
                  activeTab === "timeline"
                    ? "bg-white text-gray-900 shadow-sm"
                    : "bg-gray-200 text-gray-700"
                }`}
              >
                Timeline
              </button>
            </div>

            {activeTab === "readable" && (
              <div className="rounded bg-white p-3 text-sm text-gray-800 shadow-sm">
                <div className="mb-3 flex items-center justify-between">
                  <p className="font-semibold">Full transcript</p>
                  <span className="text-xs text-gray-500">Auto-grouped for readability</span>
                </div>
                <div className="space-y-4 leading-relaxed">
                  {paragraphs.length === 0 ? (
                    <p className="whitespace-pre-line">{data.full_text}</p>
                  ) : (
                    paragraphs.map((para, idx) => (
                      <div key={idx} className="border-l-2 border-blue-100 pl-3">
                        <p className="whitespace-pre-line">{para}</p>
                      </div>
                    ))
                  )}
                </div>
              </div>
            )}

            {activeTab === "timeline" && (
              <div className="rounded bg-white p-3 text-sm text-gray-800 shadow-sm">
                <div className="mb-3 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                  <p className="font-semibold">
                    Segments ({filteredSegments.length}/{data.segments.length})
                  </p>
                  <div className="flex items-center gap-2">
                    <div className="relative">
                      <Search className="pointer-events-none absolute left-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-gray-400" />
                      <input
                        type="text"
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                        placeholder="Search text or speaker"
                        className="w-48 rounded border border-gray-300 py-1 pl-8 pr-2 text-xs focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                      />
                    </div>
                    <span className="text-[11px] text-gray-500">
                      Duration: {formatDuration(data.duration_seconds)} | Words: {data.word_count}
                    </span>
                  </div>
                </div>
                <div className="max-h-72 space-y-2 overflow-y-auto">
                  {filteredSegments.map((segment, idx) => (
                    <div
                      key={`${segment.start}-${idx}`}
                      className="rounded border border-gray-200 bg-white p-2 text-sm shadow-[0_1px_2px_rgba(0,0,0,0.04)]"
                    >
                      <div className="mb-1 flex items-center justify-between text-xs text-gray-500">
                        <span className="inline-flex items-center rounded bg-blue-50 px-2 py-0.5 font-medium text-blue-700">
                          {formatTimestamp(segment.start)} - {formatTimestamp(segment.end)}
                        </span>
                        {segment.speaker && (
                          <span className="inline-flex items-center rounded bg-gray-100 px-2 py-0.5 text-gray-700">
                            {segment.speaker}
                          </span>
                        )}
                      </div>
                      <p className="leading-snug text-gray-800">{segment.text}</p>
                    </div>
                  ))}
                  {filteredSegments.length === 0 && (
                    <p className="text-xs text-gray-500">No segments match your search.</p>
                  )}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    );
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

        {usageSummary && (
          <div className="mb-6 grid gap-4 sm:grid-cols-2">
            <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
              <div className="flex items-center justify-between text-sm">
                <p className="font-semibold text-gray-900">Storage</p>
                <span className="text-xs text-gray-500">
                  Period ends {new Date(usageSummary.period_end).toLocaleDateString()}
                </span>
              </div>
              <div className="mt-3">
                <div className="flex items-end justify-between">
                  <div>
                    <p className="text-xl font-bold text-gray-900">
                      {formatMb(usageSummary.storage_breakdown.total_mb)}
                    </p>
                    <p className="text-xs text-gray-500">
                      of {formatMb(usageSummary.storage_breakdown.limit_mb)} used
                    </p>
                  </div>
                  <div className="text-right text-xs text-gray-600 space-y-0.5">
                    <p>Audio: {formatMb(usageSummary.storage_breakdown.audio_mb)}</p>
                    <p>Transcript (~): {formatMb(usageSummary.storage_breakdown.transcript_mb)}</p>
                    <p>On disk: {formatMb(usageSummary.storage_breakdown.disk_usage_mb)}</p>
                  </div>
                </div>
                <div className="mt-3 h-2 w-full overflow-hidden rounded-full bg-gray-200">
                  <div
                    className="h-full bg-blue-600"
                    style={{
                      width: `${Math.min(
                        Math.max(usageSummary.storage_breakdown.percentage, 0),
                        100
                      ).toFixed(0)}%`,
                    }}
                  />
                </div>
                <div className="mt-3 p-3 bg-blue-50 rounded-md border border-blue-100">
                  <p className="text-xs text-blue-700">
                    <span className="font-semibold">Potential savings:</span> Delete{" "}
                    {data?.videos.length || 0} video(s) to free{" "}
                    {formatMb(
                      (data?.videos.reduce(
                        (sum, v) =>
                          sum +
                          (v.audio_file_size_mb || 0) +
                          (v.transcript_size_mb || 0),
                        0
                      ) || 0) * 1.15
                    )}{" "}
                    (est.)
                  </p>
                </div>
              </div>
            </div>
            <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
              <div className="flex items-center justify-between text-sm">
                <p className="font-semibold text-gray-900">Processing</p>
                <span className="text-xs text-gray-500">
                  {usageSummary.counts.videos_completed}/{usageSummary.counts.videos_total} completed
                </span>
              </div>
              <div className="mt-3 grid grid-cols-2 gap-3 text-sm text-gray-800">
                <div>
                  <p className="text-xs text-gray-500">Minutes</p>
                  <p className="font-semibold">
                    {usageSummary.minutes.used.toFixed(1)} / {usageSummary.minutes.limit.toFixed(1)}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-gray-500">Messages</p>
                  <p className="font-semibold">
                    {usageSummary.messages.used} / {usageSummary.messages.limit}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-gray-500">Transcripts</p>
                  <p className="font-semibold">{usageSummary.counts.transcripts}</p>
                </div>
                <div>
                  <p className="text-xs text-gray-500">Chunks indexed</p>
                  <p className="font-semibold">{usageSummary.counts.chunks}</p>
                </div>
              </div>
              {usageSummary.vector_store && (
                <p className="mt-3 text-xs text-gray-500">
                  Vector points (all users): {usageSummary.vector_store.total_points}
                </p>
              )}
            </div>
          </div>
        )}

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
            <div className="flex items-center justify-between px-6 py-3 border-b border-gray-200">
              <div className="text-sm text-gray-600">
                Select completed videos. You'll choose what to delete to save space.
              </div>
              <div className="flex items-center space-x-2">
                <button
                  onClick={handleBulkDelete}
                  disabled={selectedVideoIds.size === 0 || bulkDeleteMutation.isPending}
                  className="inline-flex items-center px-3 py-1.5 text-xs font-medium rounded-md border border-red-200 text-red-700 hover:bg-red-50 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <Trash2 className="w-4 h-4 mr-1.5" />
                  Delete Selected ({selectedVideoIds.size})
                </button>
              </div>
            </div>
            {data?.videos.length === 0 ? (
              <div className="text-center py-12">
                <p className="text-gray-500">No videos yet. Add your first video to get started.</p>
              </div>
            ) : (
              <ul className="divide-y divide-gray-200">
                {data?.videos.map((video) => (
                  <li key={video.id} className="px-6 py-4 hover:bg-gray-50">
                    <div className="flex items-start justify-between">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center mb-2">
                          <input
                            type="checkbox"
                            className="h-4 w-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                            disabled={!isDeletable(video) || deleteMutation.isPending || bulkDeleteMutation.isPending}
                            checked={selectedVideoIds.has(video.id)}
                            onChange={(e) => toggleSelection(video.id, e.target.checked)}
                            aria-label={`Select ${video.title} for deletion`}
                          />
                          <span className="ml-2 text-xs text-gray-500">
                            {isDeletable(video) ? "Select for cleanup" : "Wait until completed"}
                          </span>
                        </div>
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
                          <span>|</span>
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

                        <div className="mt-1 text-xs text-gray-500">
                          Storage: audio {formatMb(video.audio_file_size_mb)} • transcript{" "}
                          {formatMb(video.transcript_size_mb)} • total {formatMb(video.storage_total_mb)}
                        </div>

                        {video.progress_percent !== undefined &&
                          !["completed", "failed"].includes(video.status) && (
                            <div className="mt-2">
                              <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
                                <div
                                  className="h-full bg-blue-500 transition-all"
                                  style={{
                                    width: `${Math.min(
                                      Math.max(video.progress_percent, 0),
                                      100
                                    )}%`,
                                  }}
                                />
                              </div>
                              <p className="mt-1 text-xs text-gray-500">
                                {Math.round(video.progress_percent)}% - {video.status}
                              </p>
                            </div>
                          )}

                        {/* Tags */}
                        {video.tags && video.tags.length > 0 && (
                          <div className="mt-2 flex flex-wrap gap-2">
                            {video.tags.map((tag) => (
                              <span
                                key={tag}
                                className="inline-flex items-center px-2 py-1 bg-gray-100 text-gray-700 text-xs rounded"
                              >
                                <TagIcon className="w-3 h-3 mr-1" />
                                {tag}
                              </span>
                            ))}
                          </div>
                        )}

                        {/* Action Buttons */}
                        <div className="mt-3 flex items-center gap-2">
                          <button
                            onClick={() => setAddToCollectionVideo(video)}
                            className="inline-flex items-center px-3 py-1.5 text-xs font-medium text-gray-700 bg-white border border-gray-300 rounded hover:bg-gray-50 transition-colors"
                          >
                            <FolderPlus className="w-3.5 h-3.5 mr-1.5" />
                            Add to Collection
                          </button>
                          <button
                            onClick={() => setManageTagsVideo(video)}
                            className="inline-flex items-center px-3 py-1.5 text-xs font-medium text-gray-700 bg-white border border-gray-300 rounded hover:bg-gray-50 transition-colors"
                          >
                            <TagIcon className="w-3.5 h-3.5 mr-1.5" />
                            Manage Tags
                          </button>
                          <button
                            onClick={() => toggleTranscript(video.id)}
                            disabled={video.status !== "completed"}
                            className="inline-flex items-center px-3 py-1.5 text-xs font-medium text-gray-700 bg-white border border-gray-300 rounded hover:bg-gray-50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                          >
                            {openTranscriptVideoId === video.id ? (
                              <ChevronUp className="w-3.5 h-3.5 mr-1.5" />
                            ) : (
                              <ChevronDown className="w-3.5 h-3.5 mr-1.5" />
                            )}
                            View Transcript
                          </button>
                        </div>

                        {video.error_message && (
                          <p className="mt-2 text-sm text-red-600">
                            {video.error_message}
                          </p>
                        )}

                        <TranscriptPanel
                          videoId={video.id}
                          isOpen={openTranscriptVideoId === video.id}
                        />
                      </div>
                      <div className="ml-4 flex-shrink-0">
                        <button
                          onClick={() => handleDelete(video)}
                          disabled={!isDeletable(video) || deleteMutation.isPending || bulkDeleteMutation.isPending}
                          className="p-2 text-gray-400 hover:text-red-600 focus:outline-none disabled:opacity-50 disabled:cursor-not-allowed"
                          title="Delete video"
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

        {/* Add to Collection Modal */}
        {addToCollectionVideo && (
          <AddToCollectionModal
            videoId={addToCollectionVideo.id}
            videoTitle={addToCollectionVideo.title}
            onClose={() => setAddToCollectionVideo(null)}
          />
        )}

        {/* Manage Tags Modal */}
        {manageTagsVideo && (
          <ManageTagsModal
            videoId={manageTagsVideo.id}
            videoTitle={manageTagsVideo.title}
            currentTags={manageTagsVideo.tags || []}
            onClose={() => setManageTagsVideo(null)}
          />
        )}

        {/* Delete Confirmation Modal */}
        {showDeleteModal && videosToDelete.length > 0 && (
          <DeleteConfirmationModal
            videos={videosToDelete}
            onConfirm={handleConfirmDelete}
            onCancel={() => setShowDeleteModal(false)}
            isLoading={bulkDeleteMutation.isPending}
          />
        )}
      </div>
    </MainLayout>
  );
}

