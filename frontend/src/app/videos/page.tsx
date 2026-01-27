/**
 * Videos Page - Performance Optimized
 *
 * Performance Fix: Parallel auth + data fetching (no blocking)
 * Before: Sequential auth → data (5s total)
 * After: Parallel execution (~1-2s)
 */

"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { formatDistanceToNow } from "date-fns";
import { useAuth, createParallelQueryFn, useAuthState } from "@/lib/auth";
import { MainLayout } from "@/components/layout/MainLayout";
import { videosApi } from "@/lib/api/videos";
import { usageApi } from "@/lib/api/usage";
import { subscriptionsApi } from "@/lib/api/subscriptions";
import { Video, VideoDeleteRequest, VideoListResponse, UsageSummary, QuotaUsage, CleanupOption } from "@/lib/types";
import UpgradePromptModal from "@/components/subscription/UpgradePromptModal";
import QuotaDisplay from "@/components/subscription/QuotaDisplay";
import { DeleteConfirmationModal } from "@/components/videos/DeleteConfirmationModal";
import { CancelConfirmationModal } from "@/components/videos/CancelConfirmationModal";
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
  StopCircle,
  RefreshCw,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import Link from "next/link";
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
import { cn, parseUTCDate } from "@/lib/utils";
import { useToast } from "@/hooks/use-toast";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

export default function VideosPage() {
  const authProvider = useAuth();
  const authState = useAuthState();
  const canFetch = authState.isAuthenticated;
  const { toast } = useToast();
  const [youtubeUrl, setYoutubeUrl] = useState("");
  const [addToCollectionVideos, setAddToCollectionVideos] = useState<Video[]>([]);
  const [manageTagsVideo, setManageTagsVideo] = useState<Video | null>(null);
  const [selectedVideoIds, setSelectedVideoIds] = useState<Set<string>>(new Set());
  const [openTranscriptVideoId, setOpenTranscriptVideoId] = useState<string | null>(null);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [videosToDelete, setVideosToDelete] = useState<Video[]>([]);
  const [showCancelModal, setShowCancelModal] = useState(false);
  const [videosToCancel, setVideosToCancel] = useState<Video[]>([]);
  const [isAddDialogOpen, setIsAddDialogOpen] = useState(false);
  const [showUpgradeModal, setShowUpgradeModal] = useState(false);
  const [showStorageBreakdown, setShowStorageBreakdown] = useState(false);
  const queryClient = useQueryClient();

  // Performance: Parallel auth + data fetch (no blocking on auth)
  const { data: usageSummary } = useQuery<UsageSummary>({
    queryKey: ["usage-summary"],
    queryFn: createParallelQueryFn(authProvider, () => usageApi.getSummary()),
    staleTime: 30_000,
    enabled: canFetch,
  });

  // Fetch quota for enforcement
  const { data: quota } = useQuery<QuotaUsage>({
    queryKey: ["subscription-quota"],
    queryFn: createParallelQueryFn(authProvider, () => subscriptionsApi.getQuota()),
    staleTime: 30_000,
    enabled: canFetch,
  });

  // Performance: Parallel fetch + increased polling interval
  const {
    data,
    isLoading,
    isError,
    error,
  } = useQuery<VideoListResponse>({
    queryKey: ["videos"],
    queryFn: createParallelQueryFn(authProvider, () => videosApi.list()),
    staleTime: 30 * 1000, // 30 seconds - data is reasonably fresh
    enabled: canFetch,
    refetchInterval: (query) => {
      const videos = (query.state.data as VideoListResponse)?.videos ?? [];
      const hasInFlight = videos.some(
        (video: Video) => !["completed", "failed"].includes(video.status)
      );
      return hasInFlight ? 10000 : false; // 10 seconds when processing
    },
  });

  const ingestMutation = useMutation({
    mutationFn: videosApi.ingest,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["videos"] });
      setYoutubeUrl("");
      setIsAddDialogOpen(false);
    },
    onError: (error: unknown) => {
      console.error("Video ingest failed:", error);
      // Handle quota exceeded errors where detail is an object with message property
      const detail = (error as any)?.response?.data?.detail;
      const message =
        typeof detail === 'string' ? detail :
        typeof detail === 'object' && detail?.message ? detail.message :
        (error as any)?.message ??
        "Failed to ingest video. Please try again.";
      toast({
        title: "Ingest failed",
        description: message,
        variant: "destructive",
      });
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
      toast({
        title: "Delete failed",
        description: "Failed to delete videos. Please try again.",
        variant: "destructive",
      });
    },
  });

  const cancelMutation = useMutation({
    mutationFn: async ({ videoId, cleanupOption }: { videoId: string; cleanupOption: CleanupOption }) => {
      return videosApi.cancel(videoId, cleanupOption);
    },
    onSuccess: () => {
      setShowCancelModal(false);
      setVideosToCancel([]);
      queryClient.invalidateQueries({ queryKey: ["videos"] });
      queryClient.invalidateQueries({ queryKey: ["usage-summary"] });
    },
    onError: (error) => {
      console.error("Cancel failed:", error);
      toast({
        title: "Cancel failed",
        description: "Failed to cancel video. Please try again.",
        variant: "destructive",
      });
    },
  });

  const bulkCancelMutation = useMutation({
    mutationFn: async ({ videoIds, cleanupOption }: { videoIds: string[]; cleanupOption: CleanupOption }) => {
      return videosApi.cancelBulk(videoIds, cleanupOption);
    },
    onSuccess: () => {
      setSelectedVideoIds(new Set());
      setShowCancelModal(false);
      setVideosToCancel([]);
      queryClient.invalidateQueries({ queryKey: ["videos"] });
      queryClient.invalidateQueries({ queryKey: ["usage-summary"] });
    },
    onError: (error) => {
      console.error("Bulk cancel failed:", error);
      toast({
        title: "Cancel failed",
        description: "Failed to cancel videos. Please try again.",
        variant: "destructive",
      });
    },
  });

  const reprocessMutation = useMutation({
    mutationFn: (videoId: string) => videosApi.reprocess(videoId),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["videos"] });
    },
    onError: (error) => {
      console.error("Reprocess failed:", error);
      // Handle quota exceeded errors where detail is an object with message property
      const detail = (error as any)?.response?.data?.detail;
      const message =
        typeof detail === 'string' ? detail :
        typeof detail === 'object' && detail?.message ? detail.message :
        "Failed to reprocess video. Please try again.";
      toast({
        title: "Reprocess failed",
        description: message,
        variant: "destructive",
      });
    },
  });

  const handleIngest = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!youtubeUrl.trim()) {
      return;
    }
    // Check quota before ingesting
    if (quota && quota.videos_remaining <= 0) {
      setShowUpgradeModal(true);
      setIsAddDialogOpen(false);
      return;
    }
    ingestMutation.mutate(youtubeUrl.trim());
  };

  const handleOpenIngestDialog = () => {
    // Check quota before opening dialog
    if (quota && quota.videos_remaining <= 0) {
      setShowUpgradeModal(true);
      return;
    }
    setIsAddDialogOpen(true);
  };

  const isDeletable = (video: Video) => ["completed", "failed", "canceled"].includes(video.status);

  const isCancelable = (video: Video) =>
    ["pending", "downloading", "transcribing", "chunking", "enriching", "indexing"].includes(video.status);

  const isReprocessable = (video: Video) =>
    ["pending", "failed", "canceled"].includes(video.status);

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

  const handleCancel = (video: Video) => {
    if (!isCancelable(video)) return;
    setVideosToCancel([video]);
    setShowCancelModal(true);
  };

  const handleBulkCancel = () => {
    const ids = Array.from(selectedVideoIds);
    if (ids.length === 0) return;
    const toCancel = data?.videos.filter((v) => ids.includes(v.id) && isCancelable(v)) ?? [];
    if (toCancel.length === 0) {
      toast({
        title: "No cancelable videos",
        description: "Only videos in processing states can be canceled.",
        variant: "destructive",
      });
      return;
    }
    setVideosToCancel(toCancel);
    setShowCancelModal(true);
  };

  const handleConfirmCancel = async (cleanupOption: CleanupOption) => {
    if (videosToCancel.length === 1) {
      await cancelMutation.mutateAsync({ videoId: videosToCancel[0].id, cleanupOption });
    } else {
      await bulkCancelMutation.mutateAsync({
        videoIds: videosToCancel.map((v) => v.id),
        cleanupOption,
      });
    }
  };

  const openAddToCollectionModal = (videosToAdd: Video[]) => {
    if (videosToAdd.length === 0) return;
    setAddToCollectionVideos(videosToAdd);
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
      case "canceled":
        return "border-orange-200 bg-orange-50 text-orange-700";
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
    if (value === -1) return "Unlimited";
    if (value > 0 && value < 0.1) return "<0.1 MB";
    return `${value.toFixed(1)} MB`;
  };

  const formatLimit = (value: number) => {
    if (value === -1) return "Unlimited";
    return value.toFixed(1);
  };

  const toggleTranscript = (videoId: string) => {
    setOpenTranscriptVideoId((prev) => (prev === videoId ? null : videoId));
  };

  // Activity status helpers for Phase 2 progress feedback
  const getActivityStatus = (video: Video) => {
    if (!["transcribing", "downloading", "chunking", "enriching", "indexing"].includes(video.status)) {
      return null;
    }

    const updatedAt = parseUTCDate(video.updated_at);
    const now = new Date();
    const secondsAgo = Math.floor((now.getTime() - updatedAt.getTime()) / 1000);

    if (secondsAgo < 60) {
      return { isActive: true, text: "Active now" };
    } else if (secondsAgo < 180) {
      return { isActive: true, text: `Active ${Math.floor(secondsAgo / 60)}m ago` };
    } else {
      return { isActive: false, text: `Last seen ${Math.floor(secondsAgo / 60)}m ago` };
    }
  };

  const videos = data?.videos ?? [];
  const selectedVideos = videos.filter((video) => selectedVideoIds.has(video.id));
  const TranscriptPanel = ({ videoId, isOpen }: { videoId: string; isOpen: boolean }) => {
    const [activeTab, setActiveTab] = useState<"readable" | "timeline">("readable");
    const [search, setSearch] = useState("");
    // Performance: Parallel fetch for transcript
    const { data, isLoading, isError, refetch } = useQuery({
      queryKey: ["video-transcript", videoId],
      queryFn: createParallelQueryFn(authProvider, () => videosApi.getTranscript(videoId)),
      enabled: isOpen,
    });

    if (!isOpen) return null;

    const countWords = (text: string) =>
      text
        .trim()
        .split(/\s+/)
        .filter(Boolean).length;

    const splitIntoSentences = (text: string) => {
      if (!text) return [];

      // Prefer Intl.Segmenter for more reliable sentence boundaries when available.
      if (typeof Intl !== "undefined" && (Intl as any).Segmenter) {
        try {
          const segmenter = new (Intl as any).Segmenter(data?.language || "en", {
            granularity: "sentence",
          });
          return Array.from(segmenter.segment(text)).map((s: any) => s.segment.trim());
        } catch {
          // Fall through to regex split
        }
      }

      return text
        .split(/(?<=[.!?])\s+/)
        .map((sentence) => sentence.trim())
        .filter(Boolean);
    };

    const buildParagraphs = () => {
      if (!data) return [];

      // If the transcript already has line breaks, preserve them.
      const paragraphBlocks = data.full_text
        ?.split(/\n\s*\n+/)
        .map((block) => block.trim())
        .filter(Boolean);
      if (paragraphBlocks && paragraphBlocks.length > 1) {
        return paragraphBlocks;
      }

      const lineBreakBlocks = data.full_text
        ?.split(/\r?\n/)
        .map((block) => block.trim())
        .filter(Boolean);
      if (lineBreakBlocks && lineBreakBlocks.length > 1) {
        return lineBreakBlocks;
      }

      const PARAGRAPH_BREAK_SECONDS = 8;
      const MAX_PARAGRAPH_WORDS = 60;
      const paragraphs: string[] = [];
      let currentSentences: string[] = [];
      let currentWordCount = 0;

      data.segments.forEach((segment, idx) => {
        const prev = data.segments[idx - 1];
        const gap = prev ? segment.start - prev.end : 0;
        const speakerChanged =
          prev && prev.speaker && segment.speaker && prev.speaker !== segment.speaker;
        const needHardBreak = gap > PARAGRAPH_BREAK_SECONDS || speakerChanged;

        if (needHardBreak && currentSentences.length > 0) {
          paragraphs.push(currentSentences.join(" "));
          currentSentences = [];
          currentWordCount = 0;
        }

        const sentences = splitIntoSentences(segment.text);
        sentences.forEach((sentence) => {
          const sentenceWords = countWords(sentence);
          const wouldExceed = currentWordCount + sentenceWords > MAX_PARAGRAPH_WORDS;

          if (wouldExceed && currentSentences.length > 0) {
            paragraphs.push(currentSentences.join(" "));
            currentSentences = [];
            currentWordCount = 0;
          }

          currentSentences.push(sentence);
          currentWordCount += sentenceWords;
        });
      });

      if (currentSentences.length > 0) {
        paragraphs.push(currentSentences.join(" "));
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
    <TooltipProvider>
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
            {quota && (
              <div className="text-sm">
                <QuotaDisplay
                  used={quota.videos_used}
                  limit={quota.videos_limit}
                  label="videos"
                  variant="full"
                />
              </div>
            )}
            <Dialog open={isAddDialogOpen} onOpenChange={setIsAddDialogOpen}>
              <Button
                className="gap-2"
                onClick={handleOpenIngestDialog}
                disabled={quota ? quota.videos_remaining <= 0 : false}
              >
                <Plus className="h-4 w-4" />
                Ingest video
              </Button>
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
                <div>
                  <p className="text-3xl font-semibold">
                    {formatMb(usageSummary.storage_breakdown.total_mb)}
                  </p>
                  <p className="text-sm text-muted-foreground">
                    {usageSummary.storage_breakdown.limit_mb === -1
                      ? "Unlimited storage"
                      : `of ${formatMb(usageSummary.storage_breakdown.limit_mb)} used`}
                  </p>
                </div>
                {usageSummary.storage_breakdown.limit_mb !== -1 && (
                  <Progress
                    value={Math.min(
                      Math.max(usageSummary.storage_breakdown.percentage ?? 0, 0),
                      100
                    )}
                    className="h-2"
                  />
                )}
                <button
                  type="button"
                  onClick={() => setShowStorageBreakdown(!showStorageBreakdown)}
                  className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
                >
                  {showStorageBreakdown ? (
                    <ChevronUp className="h-3.5 w-3.5" />
                  ) : (
                    <ChevronDown className="h-3.5 w-3.5" />
                  )}
                  View breakdown
                </button>
                <div
                  className={cn(
                    "overflow-hidden transition-all duration-200",
                    showStorageBreakdown ? "max-h-40 opacity-100" : "max-h-0 opacity-0"
                  )}
                >
                  <div className="rounded-lg border bg-muted/30 p-3 space-y-2">
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-muted-foreground">Disk (audio/transcripts)</span>
                      <span className="font-medium">{formatMb(usageSummary.storage_breakdown.disk_usage_mb)}</span>
                    </div>
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-muted-foreground">Database (chunks/messages)</span>
                      <span className="font-medium">{formatMb(usageSummary.storage_breakdown.database_mb)}</span>
                    </div>
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-muted-foreground">Vector index</span>
                      <span className="font-medium">{formatMb(usageSummary.storage_breakdown.vector_mb)}</span>
                    </div>
                  </div>
                </div>
                <div className="rounded-lg border bg-muted/30 p-3 text-xs text-muted-foreground">
                  Delete {videos.length} video(s) to free approximately {formatMb(
                    videos.reduce((sum, v) => sum + (v.storage_total_mb || 0), 0)
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
                    {usageSummary.minutes.limit === -1
                      ? `${usageSummary.minutes.used.toFixed(1)} / Unlimited`
                      : `${usageSummary.minutes.used.toFixed(1)} / ${usageSummary.minutes.limit.toFixed(1)}`}
                  </p>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-wide">Messages</p>
                  <p className="text-lg font-semibold text-foreground">
                    {usageSummary.messages.limit === -1
                      ? `${usageSummary.messages.used} / Unlimited`
                      : `${usageSummary.messages.used} / ${usageSummary.messages.limit}`}
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
            <div className="flex flex-col items-end gap-2 text-sm text-muted-foreground sm:flex-row sm:items-center sm:gap-4">
              <div className="text-sm text-muted-foreground">
                {selectedVideoIds.size > 0
                  ? `${selectedVideoIds.size} video(s) selected`
                  : "Select completed videos to enable cleanup."}
              </div>
              {selectedVideos.length > 0 && (
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    className="gap-1"
                    onClick={() => openAddToCollectionModal(selectedVideos)}
                  >
                    <FolderPlus className="h-3.5 w-3.5" />
                    Add to collection
                  </Button>
                  {selectedVideos.some(isCancelable) && (
                    <Button
                      variant="outline"
                      size="sm"
                      className="gap-2 text-orange-600 border-orange-300 hover:bg-orange-50"
                      onClick={handleBulkCancel}
                      disabled={bulkCancelMutation.isPending}
                    >
                      <StopCircle className="h-4 w-4" />
                      Cancel processing ({selectedVideos.filter(isCancelable).length})
                    </Button>
                  )}
                  <Button
                    variant="outline"
                    size="sm"
                    className="gap-2"
                    onClick={handleBulkDelete}
                    disabled={bulkDeleteMutation.isPending}
                  >
                    <Trash2 className="h-4 w-4" />
                    Delete selected ({selectedVideoIds.size})
                  </Button>
                </div>
              )}
            </div>
          </CardHeader>
          <CardContent className="p-0">
            {!canFetch ? (
              <div className="py-12 text-center text-sm text-muted-foreground">
                <p className="mb-4">Sign in to view your video library.</p>
                <div className="flex flex-col items-center justify-center gap-2 sm:flex-row">
                  <Button asChild>
                    <Link href="/sign-up">Create account</Link>
                  </Button>
                  <Button asChild variant="outline">
                    <Link href="/login">Sign in</Link>
                  </Button>
                </div>
              </div>
            ) : isLoading ? (
              <div className="flex items-center justify-center gap-2 py-12 text-muted-foreground">
                <Loader2 className="h-5 w-5 animate-spin" />
                Loading videos...
              </div>
            ) : isError ? (
              <div className="py-12 text-center text-sm text-destructive">
                Unable to load videos.{" "}
                {error instanceof Error ? error.message : "Please try again."}
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
                    <TableHead className="w-[40%]">Video</TableHead>
                    <TableHead className="w-[15%]">Status</TableHead>
                    <TableHead className="w-[15%]">Storage</TableHead>
                    <TableHead className="w-[30%] text-right">Actions</TableHead>
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
                                    parseUTCDate(video.created_at)
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
                              !["completed", "failed", "canceled"].includes(video.status) && (
                                <div className="space-y-1">
                                  <div className="relative overflow-hidden rounded-full">
                                    <Progress value={video.progress_percent} className="h-1.5" />
                                    {["transcribing", "downloading", "chunking", "enriching", "indexing"].includes(video.status) && (
                                      <div
                                        className="absolute inset-0 bg-gradient-to-r from-transparent via-white/30 to-transparent animate-shimmer"
                                        style={{ backgroundSize: "200% 100%" }}
                                      />
                                    )}
                                  </div>
                                  <p className="text-xs text-muted-foreground flex items-center gap-1.5">
                                    {["transcribing", "downloading", "chunking", "enriching", "indexing"].includes(video.status) && (
                                      <span className="inline-block w-1.5 h-1.5 rounded-full bg-sky-500 animate-pulse" />
                                    )}
                                    {Math.round(video.progress_percent)}% - {video.status}
                                  </p>
                                  {/* Activity status for long-running transcription */}
                                  {video.status === "transcribing" && getActivityStatus(video) && (
                                    <div className="mt-1 flex items-center gap-1.5 text-xs text-muted-foreground">
                                      {getActivityStatus(video)?.isActive ? (
                                        <span className="inline-block w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
                                      ) : (
                                        <span className="inline-block w-1.5 h-1.5 rounded-full bg-yellow-500" />
                                      )}
                                      <span>{getActivityStatus(video)?.text}</span>
                                    </div>
                                  )}
                                </div>
                              )}
                          </TableCell>
                          <TableCell className="text-sm text-muted-foreground">
                            <Tooltip>
                              <TooltipTrigger asChild>
                                <span className="cursor-help border-b border-dashed border-muted-foreground/50">
                                  {formatMb(video.storage_total_mb)}
                                </span>
                              </TooltipTrigger>
                              <TooltipContent side="top" className="bg-popover text-popover-foreground border shadow-md">
                                <div className="space-y-1 text-xs">
                                  <div className="flex justify-between gap-4">
                                    <span className="text-muted-foreground">Transcript</span>
                                    <span className="font-medium">{formatMb(video.transcript_size_mb)}</span>
                                  </div>
                                  <div className="flex justify-between gap-4">
                                    <span className="text-muted-foreground">Chunks</span>
                                    <span className="font-medium">{formatMb(video.chunk_storage_mb)}</span>
                                  </div>
                                  <div className="flex justify-between gap-4">
                                    <span className="text-muted-foreground">Vectors</span>
                                    <span className="font-medium">{formatMb(video.vector_storage_mb)}</span>
                                  </div>
                                </div>
                              </TooltipContent>
                            </Tooltip>
                          </TableCell>
                          <TableCell className="text-right">
                            <div className="flex flex-wrap items-center justify-end gap-2 sm:flex-nowrap">
                              <Button
                                variant="outline"
                                size="sm"
                                className="gap-1"
                                onClick={() => openAddToCollectionModal([video])}
                              >
                                <FolderPlus className="h-3.5 w-3.5" />
                                Add to collection
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
                              {isCancelable(video) && (
                                <Button
                                  variant="ghost"
                                  size="icon"
                                  className="text-muted-foreground hover:text-orange-600"
                                  onClick={() => handleCancel(video)}
                                  disabled={
                                    cancelMutation.isPending ||
                                    bulkCancelMutation.isPending
                                  }
                                >
                                  <StopCircle className="h-4 w-4" />
                                  <span className="sr-only">Cancel</span>
                                </Button>
                              )}
                              {isReprocessable(video) && (
                                <Button
                                  variant="ghost"
                                  size="icon"
                                  className="text-muted-foreground hover:text-blue-600"
                                  onClick={() => reprocessMutation.mutate(video.id)}
                                  disabled={reprocessMutation.isPending}
                                  title="Reprocess video"
                                >
                                  <RefreshCw className={`h-4 w-4 ${reprocessMutation.isPending ? "animate-spin" : ""}`} />
                                  <span className="sr-only">Reprocess</span>
                                </Button>
                              )}
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

        {addToCollectionVideos.length > 0 && (
          <AddToCollectionModal
            videoIds={addToCollectionVideos.map((video) => video.id)}
            videoTitle={
              addToCollectionVideos.length === 1 ? addToCollectionVideos[0].title : undefined
            }
            onClose={() => setAddToCollectionVideos([])}
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

        {showCancelModal && videosToCancel.length > 0 && (
          <CancelConfirmationModal
            videos={videosToCancel}
            onConfirm={handleConfirmCancel}
            onCancel={() => {
              setShowCancelModal(false);
              setVideosToCancel([]);
            }}
            isLoading={cancelMutation.isPending || bulkCancelMutation.isPending}
          />
        )}

        <UpgradePromptModal
          quotaType="videos"
          isOpen={showUpgradeModal}
          onClose={() => setShowUpgradeModal(false)}
        />
      </div>
    </MainLayout>
    </TooltipProvider>
  );
}
