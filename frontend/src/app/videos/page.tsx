"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { formatDistanceToNow } from "date-fns";
import { MainLayout } from "@/components/layout/MainLayout";
import { videosApi } from "@/lib/api/videos";
import { usageApi } from "@/lib/api/usage";
import { Video, VideoDeleteRequest } from "@/lib/types";
import { DeleteConfirmationModal } from "@/components/videos/DeleteConfirmationModal";
import { AddToCollectionModal } from "@/components/videos/AddToCollectionModal";
import { ManageTagsModal } from "@/components/videos/ManageTagsModal";
import {
  Plus,
  Trash2,
  ExternalLink,
  Loader2,
  FolderPlus,
  Tag as TagIcon,
  FileText,
  Copy,
  Download,
  Search,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Progress } from "@/components/ui/progress";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

export default function VideosPage() {
  const [youtubeUrl, setYoutubeUrl] = useState("");
  const [addToCollectionVideo, setAddToCollectionVideo] = useState<Video | null>(null);
  const [manageTagsVideo, setManageTagsVideo] = useState<Video | null>(null);
  const [selectedVideoIds, setSelectedVideoIds] = useState<Set<string>>(new Set());
  const [openTranscriptVideoId, setOpenTranscriptVideoId] = useState<string | null>(null);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [videosToDelete, setVideosToDelete] = useState<Video[]>([]);
  const [isAddDialogOpen, setIsAddDialogOpen] = useState(false);
  const queryClient = useQueryClient();

  const { data: usageSummary } = useQuery({
    queryKey: ["usage-summary"],
    queryFn: () => usageApi.getSummary(),
    staleTime: 30_000,
  });

  const { data, isLoading } = useQuery({
    queryKey: ["videos"],
    queryFn: () => videosApi.list(),
    refetchInterval: (query) => {
      const videos = query.state.data?.videos ?? [];
      const hasInFlight = videos.some(
        (video) => !["completed", "failed"].includes(video.status)
      );
      return hasInFlight ? 2000 : false;
    },
  });

  const ingestMutation = useMutation({
    mutationFn: videosApi.ingest,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["videos"] });
      setYoutubeUrl("");
      setIsAddDialogOpen(false);
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

  const handleIngest = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!youtubeUrl.trim()) {
      return;
    }
    ingestMutation.mutate(youtubeUrl.trim());
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
    const toDelete = data?.videos.filter((v) => ids.includes(v.id)) ?? [];
    setVideosToDelete(toDelete);
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

  const getStatusBadgeClass = (status: Video["status"]) => {
    switch (status) {
      case "completed":
        return "border-emerald-200 bg-emerald-50 text-emerald-700";
      case "failed":
        return "border-destructive/40 bg-destructive/10 text-destructive";
      case "processing":
      case "pending":
      case "downloading":
      case "transcribing":
      case "chunking":
      case "enriching":
      case "indexing":
        return "border-sky-200 bg-sky-50 text-sky-700";
      default:
        return "border-border bg-muted text-foreground";
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
      return `${hrs}:${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
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

  const videos = data?.videos ?? [];
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
      <div className="space-y-4 rounded-lg border bg-muted/20 p-4">
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div className="flex items-center gap-2 text-sm font-medium text-foreground">
            <FileText className="h-4 w-4" />
            Transcript
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={handleCopy}
              disabled={!data}
              className="gap-1"
            >
              <Copy className="h-3.5 w-3.5" />
              Copy
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={handleDownload}
              disabled={!data}
              className="gap-1"
            >
              <Download className="h-3.5 w-3.5" />
              Download
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => refetch()}
              disabled={isLoading}
            >
              Refresh
            </Button>
          </div>
        </div>

        {isLoading && (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            Loading transcript...
          </div>
        )}

        {isError && (
          <div className="text-sm text-destructive">
            Transcript not available yet. Try again after processing finishes.
          </div>
        )}

        {data && (
          <div className="space-y-3 text-sm text-muted-foreground">
            <div className="flex flex-wrap items-center gap-2 text-xs font-medium">
              {data.language && (
                <Badge variant="secondary" className="text-xs">
                  Language: {data.language}
                </Badge>
              )}
              <Badge variant="secondary" className="text-xs">
                Duration: {formatDuration(data.duration_seconds)}
              </Badge>
              <Badge variant="secondary" className="text-xs">
                Words: {data.word_count}
              </Badge>
            </div>

            <div className="flex gap-2">
              <Button
                variant={activeTab === "readable" ? "default" : "outline"}
                size="sm"
                onClick={() => setActiveTab("readable")}
              >
                Readable
              </Button>
              <Button
                variant={activeTab === "timeline" ? "default" : "outline"}
                size="sm"
                onClick={() => setActiveTab("timeline")}
              >
                Timeline
              </Button>
            </div>

            {activeTab === "readable" && (
              <div className="space-y-4 rounded-lg border bg-background p-4 text-foreground">
                <div className="text-xs uppercase tracking-wide text-muted-foreground">
                  Auto-grouped for readability
                </div>
                <div className="space-y-4 leading-relaxed">
                  {paragraphs.length === 0 ? (
                    <p className="whitespace-pre-line">{data.full_text}</p>
                  ) : (
                    paragraphs.map((para, idx) => (
                      <div key={idx} className="border-l-2 border-primary/30 pl-3">
                        <p className="whitespace-pre-line">{para}</p>
                      </div>
                    ))
                  )}
                </div>
              </div>
            )}

            {activeTab === "timeline" && (
              <div className="space-y-3 rounded-lg border bg-background p-4 text-foreground">
                <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                  <p className="text-sm font-medium">
                    Segments ({filteredSegments.length}/{data.segments.length})
                  </p>
                  <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
                    <div className="relative">
                      <Search className="pointer-events-none absolute left-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
                      <Input
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                        placeholder="Search text or speaker"
                        className="w-52 pl-8"
                      />
                    </div>
                    <span className="text-xs text-muted-foreground">
                      Duration {formatDuration(data.duration_seconds)} | Words {data.word_count}
                    </span>
                  </div>
                </div>
                <div className="max-h-72 space-y-2 overflow-y-auto rounded-md border bg-muted/40 p-2">
                  {filteredSegments.map((segment, idx) => (
                    <div
                      key={`${segment.start}-${idx}`}
                      className="rounded-md border bg-background p-2 shadow-sm"
                    >
                      <div className="mb-1 flex items-center justify-between text-[11px] text-muted-foreground">
                        <span className="inline-flex items-center rounded-full bg-primary/10 px-2 py-0.5 font-medium text-primary">
                          {formatTimestamp(segment.start)} - {formatTimestamp(segment.end)}
                        </span>
                        {segment.speaker && (
                          <span className="inline-flex items-center rounded-full bg-muted px-2 py-0.5">
                            {segment.speaker}
                          </span>
                        )}
                      </div>
                      <p className="text-sm text-foreground">{segment.text}</p>
                    </div>
                  ))}
                  {filteredSegments.length === 0 && (
                    <p className="text-xs text-muted-foreground">No segments match your search.</p>
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
      <div className="space-y-8">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="space-y-1">
            <p className="text-sm font-medium text-muted-foreground">Pipeline overview</p>
            <h1 className="text-3xl font-semibold tracking-tight">Video transcripts</h1>
            <p className="text-sm text-muted-foreground">
              Track ingestion, storage, and transcript quality across your workspace.
            </p>
          </div>
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
            <Button
              variant="outline"
              size="sm"
              disabled={selectedVideoIds.size === 0 || bulkDeleteMutation.isPending}
              onClick={handleBulkDelete}
              className="gap-2"
            >
              <Trash2 className="h-4 w-4" />
              Delete selected ({selectedVideoIds.size})
            </Button>
            <Dialog open={isAddDialogOpen} onOpenChange={setIsAddDialogOpen}>
              <DialogTrigger asChild>
                <Button className="gap-2">
                  <Plus className="h-4 w-4" />
                  Ingest video
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Ingest a YouTube video</DialogTitle>
                  <DialogDescription>
                    We&apos;ll fetch the media, transcribe it, and index the transcript for search.
                  </DialogDescription>
                </DialogHeader>
                <form onSubmit={handleIngest} className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="youtube-url">YouTube URL</Label>
                    <Input
                      id="youtube-url"
                      type="url"
                      placeholder="https://www.youtube.com/watch?v=..."
                      value={youtubeUrl}
                      onChange={(e) => setYoutubeUrl(e.target.value)}
                      required
                    />
                  </div>
                  <DialogFooter>
                    <Button
                      type="button"
                      variant="ghost"
                      onClick={() => setIsAddDialogOpen(false)}
                    >
                      Cancel
                    </Button>
                    <Button type="submit" disabled={ingestMutation.isPending} className="gap-2">
                      {ingestMutation.isPending && (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      )}
                      Ingest video
                    </Button>
                  </DialogFooter>
                </form>
              </DialogContent>
            </Dialog>
          </div>
        </div>

        {usageSummary && (
          <div className="grid gap-4 md:grid-cols-2">
            <Card>
              <CardHeader className="flex flex-col gap-1">
                <CardTitle>Storage</CardTitle>
                <CardDescription>
                  Period ends {new Date(usageSummary.period_end).toLocaleDateString()}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex items-end justify-between">
                  <div>
                    <p className="text-3xl font-semibold">
                      {formatMb(usageSummary.storage_breakdown.total_mb)}
                    </p>
                    <p className="text-sm text-muted-foreground">
                      of {formatMb(usageSummary.storage_breakdown.limit_mb)} used
                    </p>
                  </div>
                  <div className="text-sm text-muted-foreground">
                    <p>Audio: {formatMb(usageSummary.storage_breakdown.audio_mb)}</p>
                    <p>Transcript: {formatMb(usageSummary.storage_breakdown.transcript_mb)}</p>
                    <p>On disk: {formatMb(usageSummary.storage_breakdown.disk_usage_mb)}</p>
                  </div>
                </div>
                <Progress
                  value={Math.min(
                    Math.max(usageSummary.storage_breakdown.percentage ?? 0, 0),
                    100
                  )}
                  className="h-2"
                />
                <div className="rounded-lg border bg-muted/30 p-3 text-xs text-muted-foreground">
                  Delete {videos.length} video(s) to free approximately {formatMb(
                    (videos.reduce(
                      (sum, v) =>
                        sum + (v.audio_file_size_mb || 0) + (v.transcript_size_mb || 0),
                      0
                    ) || 0) * 1.15
                  )}.
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="flex flex-col gap-1">
                <CardTitle>Processing</CardTitle>
                <CardDescription>
                  {usageSummary.counts.videos_completed}/{usageSummary.counts.videos_total} completed
                </CardDescription>
              </CardHeader>
              <CardContent className="grid gap-4 text-sm text-muted-foreground sm:grid-cols-2">
                <div>
                  <p className="text-xs uppercase tracking-wide">Minutes</p>
                  <p className="text-lg font-semibold text-foreground">
                    {usageSummary.minutes.used.toFixed(1)} / {usageSummary.minutes.limit.toFixed(1)}
                  </p>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-wide">Messages</p>
                  <p className="text-lg font-semibold text-foreground">
                    {usageSummary.messages.used} / {usageSummary.messages.limit}
                  </p>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-wide">Transcripts</p>
                  <p className="text-lg font-semibold text-foreground">
                    {usageSummary.counts.transcripts}
                  </p>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-wide">Chunks indexed</p>
                  <p className="text-lg font-semibold text-foreground">
                    {usageSummary.counts.chunks}
                  </p>
                </div>
                {usageSummary.vector_store && (
                  <div className="sm:col-span-2">
                    <p className="text-xs uppercase tracking-wide">Vector store</p>
                    <p className="text-lg font-semibold text-foreground">
                      {usageSummary.vector_store.total_points} points indexed
                    </p>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        )}
        <Card>
          <CardHeader className="flex flex-col gap-2 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <CardTitle>Library</CardTitle>
              <CardDescription>
                Select completed videos to clean up storage or open transcripts inline.
              </CardDescription>
            </div>
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              {selectedVideoIds.size > 0
                ? `${selectedVideoIds.size} video(s) selected`
                : "Select completed videos to enable cleanup."}
            </div>
          </CardHeader>
          <CardContent className="p-0">
            {isLoading ? (
              <div className="flex items-center justify-center gap-2 py-12 text-muted-foreground">
                <Loader2 className="h-5 w-5 animate-spin" />
                Loading videos...
              </div>
            ) : videos.length === 0 ? (
              <div className="py-12 text-center text-sm text-muted-foreground">
                No videos yet. Ingest your first YouTube URL to get started.
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-12">
                      <span className="sr-only">Select</span>
                    </TableHead>
                    <TableHead>Video</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Storage</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {videos.map((video) => {
                    const isSelected = selectedVideoIds.has(video.id);
                    return (
                      <>
                        <TableRow key={video.id} className="align-top">
                          <TableCell>
                            <Checkbox
                              disabled={
                                !isDeletable(video) ||
                                deleteMutation.isPending ||
                                bulkDeleteMutation.isPending
                              }
                              checked={isSelected}
                              onCheckedChange={(checked) =>
                                toggleSelection(video.id, checked === true)
                              }
                              aria-label={`Select ${video.title} for deletion`}
                            />
                          </TableCell>
                          <TableCell className="space-y-2">
                            <div className="flex items-center gap-3">
                              <div>
                                <p className="font-medium leading-none">{video.title}</p>
                                <div className="text-xs text-muted-foreground">
                                  {formatDuration(video.duration_seconds)} - Added {formatDistanceToNow(
                                    new Date(video.created_at)
                                  )} ago
                                </div>
                              </div>
                            </div>
                            <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                              <a
                                href={video.youtube_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="inline-flex items-center gap-1 text-primary"
                              >
                                <ExternalLink className="h-3.5 w-3.5" />
                                View on YouTube
                              </a>
                              {video.tags?.map((tag) => (
                                <Badge
                                  key={tag}
                                  variant="secondary"
                                  className="flex items-center gap-1 text-[11px]"
                                >
                                  <TagIcon className="h-3 w-3" />
                                  {tag}
                                </Badge>
                              ))}
                            </div>
                            {video.error_message && (
                              <p className="text-sm text-destructive">{video.error_message}</p>
                            )}
                          </TableCell>
                          <TableCell className="space-y-2">
                            <Badge
                              variant="outline"
                              className={cn("capitalize", getStatusBadgeClass(video.status))}
                            >
                              {video.status}
                            </Badge>
                            {video.progress_percent !== undefined &&
                              !["completed", "failed"].includes(video.status) && (
                                <div className="space-y-1">
                                  <Progress value={video.progress_percent} className="h-1.5" />
                                  <p className="text-xs text-muted-foreground">
                                    {Math.round(video.progress_percent)}% - {video.status}
                                  </p>
                                </div>
                              )}
                          </TableCell>
                          <TableCell className="text-sm text-muted-foreground">
                            <div>Audio: {formatMb(video.audio_file_size_mb)}</div>
                            <div>Transcript: {formatMb(video.transcript_size_mb)}</div>
                            <div className="font-medium text-foreground">
                              Total: {formatMb(video.storage_total_mb)}
                            </div>
                          </TableCell>
                          <TableCell className="text-right">
                            <div className="flex flex-col items-end gap-2">
                              <div className="flex flex-wrap justify-end gap-2">
                                <Button
                                  variant="outline"
                                  size="sm"
                                  className="gap-1"
                                  onClick={() => setAddToCollectionVideo(video)}
                                >
                                  <FolderPlus className="h-3.5 w-3.5" />
                                  Collection
                                </Button>
                                <Button
                                  variant="outline"
                                  size="sm"
                                  className="gap-1"
                                  onClick={() => setManageTagsVideo(video)}
                                >
                                  <TagIcon className="h-3.5 w-3.5" />
                                  Tags
                                </Button>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  className="gap-1"
                                  onClick={() => toggleTranscript(video.id)}
                                  disabled={video.status !== "completed"}
                                >
                                  {openTranscriptVideoId === video.id ? (
                                    <ChevronUp className="h-4 w-4" />
                                  ) : (
                                    <ChevronDown className="h-4 w-4" />
                                  )}
                                  Transcript
                                </Button>
                              </div>
                              <Button
                                variant="ghost"
                                size="icon"
                                className="text-muted-foreground hover:text-destructive"
                                onClick={() => handleDelete(video)}
                                disabled={
                                  !isDeletable(video) ||
                                  deleteMutation.isPending ||
                                  bulkDeleteMutation.isPending
                                }
                              >
                                <Trash2 className="h-4 w-4" />
                                <span className="sr-only">Delete</span>
                              </Button>
                            </div>
                          </TableCell>
                        </TableRow>
                        {openTranscriptVideoId === video.id && (
                          <TableRow key={`${video.id}-transcript`}>
                            <TableCell colSpan={5}>
                              <TranscriptPanel
                                videoId={video.id}
                                isOpen={openTranscriptVideoId === video.id}
                              />
                            </TableCell>
                          </TableRow>
                        )}
                      </>
                    );
                  })}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>

        {addToCollectionVideo && (
          <AddToCollectionModal
            videoId={addToCollectionVideo.id}
            videoTitle={addToCollectionVideo.title}
            onClose={() => setAddToCollectionVideo(null)}
          />
        )}

        {manageTagsVideo && (
          <ManageTagsModal
            videoId={manageTagsVideo.id}
            videoTitle={manageTagsVideo.title}
            currentTags={manageTagsVideo.tags || []}
            onClose={() => setManageTagsVideo(null)}
          />
        )}

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
