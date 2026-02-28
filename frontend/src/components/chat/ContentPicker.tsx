"use client";

import { useState, useMemo } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { videosApi } from "@/lib/api/videos";
import { contentApi } from "@/lib/api/content";
import { getCollections } from "@/lib/api/collections";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Loader2, Search, Video, FileText, Folder, Upload, Link2, MessageSquare } from "lucide-react";
import { cn } from "@/lib/utils";
import { useToast } from "@/hooks/use-toast";
import { AddContentPanel } from "@/components/videos/AddContentPanel";
import type { Video as VideoType } from "@/lib/types";

interface ContentItem {
  id: string;
  title: string;
  type: "video" | "document";
  status: string;
  duration_seconds?: number;
  page_count?: number;
  channel_name?: string;
  thumbnail_url?: string;
}

type TabFilter = "all" | "videos" | "documents";

export interface ContentPickerProps {
  selectedIds: string[];
  selectedCollectionId: string;
  onSelectionChange: (ids: string[]) => void;
  onCollectionChange: (collectionId: string) => void;
  onStartChat: () => void;
  isCreating: boolean;
  enabled: boolean;
}

const PROCESSING_STATUSES = new Set([
  "pending",
  "downloading",
  "transcribing",
  "chunking",
  "enriching",
  "indexing",
]);

export function ContentPicker({
  selectedIds,
  selectedCollectionId,
  onSelectionChange,
  onCollectionChange,
  onStartChat,
  isCreating,
  enabled,
}: ContentPickerProps) {
  const [searchTerm, setSearchTerm] = useState("");
  const [tabFilter, setTabFilter] = useState<TabFilter>("all");
  const [addPanelOpen, setAddPanelOpen] = useState(false);
  const [addPanelTab, setAddPanelTab] = useState<string>("url");

  const queryClient = useQueryClient();
  const { toast } = useToast();

  const { data: videosData, isLoading: videosLoading } = useQuery({
    queryKey: ["videos-completed"],
    queryFn: () => videosApi.list(0, 200, "completed"),
    enabled,
    staleTime: 60 * 1000,
  });

  const { data: documentsData, isLoading: documentsLoading } = useQuery({
    queryKey: ["content-completed"],
    queryFn: () => contentApi.list(0, 200, undefined, "completed"),
    enabled,
    staleTime: 60 * 1000,
  });

  const { data: collectionsData, isLoading: collectionsLoading } = useQuery({
    queryKey: ["collections"],
    queryFn: () => getCollections(),
    enabled,
    staleTime: 60 * 1000,
  });

  // Fetch recent videos (all statuses) to find processing items
  const { data: recentVideosData } = useQuery({
    queryKey: ["videos-recent-all"],
    queryFn: () => videosApi.list(0, 20),
    enabled,
    refetchInterval: 10_000,
  });

  // Fetch recent documents (all statuses) to find processing items
  const { data: recentDocsData } = useQuery({
    queryKey: ["content-recent-all"],
    queryFn: () => contentApi.list(0, 20),
    enabled,
    refetchInterval: 10_000,
  });

  const isLoading = videosLoading || documentsLoading;

  // Merge videos and documents into unified list
  const allContent = useMemo<ContentItem[]>(() => {
    const items: ContentItem[] = [];

    if (videosData?.videos) {
      for (const v of videosData.videos) {
        if (v.status === "completed") {
          items.push({
            id: v.id,
            title: v.title || "Untitled video",
            type: "video",
            status: v.status,
            duration_seconds: v.duration_seconds,
            channel_name: v.channel_name,
            thumbnail_url: v.thumbnail_url,
          });
        }
      }
    }

    if (documentsData?.items) {
      for (const d of documentsData.items) {
        if (d.status === "completed") {
          items.push({
            id: d.id,
            title: d.title || "Untitled document",
            type: "document",
            status: d.status,
            page_count: d.page_count,
          });
        }
      }
    }

    return items;
  }, [videosData, documentsData]);

  // Processing items (in-progress, not yet completed)
  const processingItems = useMemo<ContentItem[]>(() => {
    const items: ContentItem[] = [];
    const completedIds = new Set(allContent.map((i) => i.id));

    if (recentVideosData?.videos) {
      for (const v of recentVideosData.videos) {
        if (PROCESSING_STATUSES.has(v.status) && !completedIds.has(v.id)) {
          items.push({
            id: v.id,
            title: v.title || "Untitled video",
            type: "video",
            status: v.status,
          });
        }
      }
    }

    if (recentDocsData?.items) {
      for (const d of recentDocsData.items) {
        if (PROCESSING_STATUSES.has(d.status) && !completedIds.has(d.id)) {
          items.push({
            id: d.id,
            title: d.title || "Untitled document",
            type: "document",
            status: d.status,
          });
        }
      }
    }

    return items;
  }, [recentVideosData, recentDocsData, allContent]);

  // When processing items become completed, refetch the completed lists
  // (handled by refetchInterval on recent queries + staleTime on completed queries)

  // Filtered items based on search and tab
  const filteredContent = useMemo(() => {
    let items = allContent;

    if (tabFilter === "videos") {
      items = items.filter((i) => i.type === "video");
    } else if (tabFilter === "documents") {
      items = items.filter((i) => i.type === "document");
    }

    if (searchTerm) {
      const term = searchTerm.toLowerCase();
      items = items.filter(
        (i) =>
          i.title.toLowerCase().includes(term) ||
          i.channel_name?.toLowerCase().includes(term)
      );
    }

    return items;
  }, [allContent, tabFilter, searchTerm]);

  const toggleItem = (id: string) => {
    if (selectedCollectionId) {
      onCollectionChange("");
    }
    onSelectionChange(
      selectedIds.includes(id)
        ? selectedIds.filter((x) => x !== id)
        : [...selectedIds, id]
    );
  };

  const selectAll = () => {
    if (selectedCollectionId) {
      onCollectionChange("");
    }
    onSelectionChange(filteredContent.map((i) => i.id));
  };

  const clearSelection = () => {
    onSelectionChange([]);
    onCollectionChange("");
  };

  const formatDuration = (seconds?: number) => {
    if (!seconds) return "";
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = seconds % 60;
    if (h > 0) return `${h}:${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
    return `${m}:${s.toString().padStart(2, "0")}`;
  };

  const openAddPanel = (tab: string) => {
    setAddPanelTab(tab);
    setAddPanelOpen(true);
  };

  const handleAddSuccess = () => {
    queryClient.invalidateQueries({ queryKey: ["videos-completed"] });
    queryClient.invalidateQueries({ queryKey: ["content-completed"] });
    queryClient.invalidateQueries({ queryKey: ["videos-recent-all"] });
    queryClient.invalidateQueries({ queryKey: ["content-recent-all"] });
    toast({
      title: "Content added",
      description: "It will appear here once processing completes.",
    });
  };

  const hasSelection = selectedIds.length > 0 || selectedCollectionId;
  const videoCount = allContent.filter((i) => i.type === "video").length;
  const docCount = allContent.filter((i) => i.type === "document").length;

  return (
    <div className="flex flex-col items-center justify-center gap-8 py-8">
      <div className="text-center space-y-2">
        <div className="flex h-14 w-14 items-center justify-center rounded-full bg-primary/10 mx-auto">
          <MessageSquare className="h-7 w-7 text-primary" />
        </div>
        <h1 className="text-2xl font-semibold">Start a new chat</h1>
        <p className="text-sm text-muted-foreground max-w-md">
          Select content from your library to chat about, or pick a collection.
        </p>
      </div>

      {/* Quick actions — open AddContentPanel inline */}
      <div className="flex gap-3">
        <Button
          variant="outline"
          size="sm"
          className="gap-2"
          onClick={() => openAddPanel("upload")}
        >
          <Upload className="h-4 w-4" />
          Upload document
        </Button>
        <Button
          variant="outline"
          size="sm"
          className="gap-2"
          onClick={() => openAddPanel("url")}
        >
          <Link2 className="h-4 w-4" />
          Add YouTube video
        </Button>
      </div>

      {/* Collections quick-select */}
      {collectionsData && collectionsData.collections.length > 0 && (
        <div className="w-full max-w-2xl space-y-2">
          <p className="text-xs font-medium text-muted-foreground px-1">Collections</p>
          <div className="flex flex-wrap gap-2">
            {collectionsData.collections.map((c) => (
              <Button
                key={c.id}
                variant={selectedCollectionId === c.id ? "default" : "outline"}
                size="sm"
                className="gap-1.5"
                onClick={() => {
                  if (selectedCollectionId === c.id) {
                    onCollectionChange("");
                  } else {
                    onCollectionChange(c.id);
                    onSelectionChange([]);
                  }
                }}
              >
                <Folder className="h-3.5 w-3.5" />
                {c.name}
                <Badge variant="secondary" className="ml-1 text-[10px]">
                  {c.video_count}
                </Badge>
              </Button>
            ))}
          </div>
        </div>
      )}

      {/* Divider */}
      {collectionsData && collectionsData.collections.length > 0 && (
        <div className="flex items-center gap-3 w-full max-w-2xl">
          <div className="flex-1 border-t" />
          <span className="text-xs text-muted-foreground">or pick from library</span>
          <div className="flex-1 border-t" />
        </div>
      )}

      {/* Tab filter + search */}
      <div className="w-full max-w-2xl space-y-3">
        <div className="flex items-center gap-2">
          <div className="flex rounded-md border bg-muted/30 p-0.5">
            {[
              { value: "all" as const, label: "All", count: allContent.length },
              { value: "videos" as const, label: "Videos", count: videoCount },
              { value: "documents" as const, label: "Docs", count: docCount },
            ].map((tab) => (
              <button
                key={tab.value}
                onClick={() => setTabFilter(tab.value)}
                className={cn(
                  "px-3 py-1 text-xs font-medium rounded-sm transition-colors",
                  tabFilter === tab.value
                    ? "bg-background text-foreground shadow-sm"
                    : "text-muted-foreground hover:text-foreground"
                )}
              >
                {tab.label} ({tab.count})
              </button>
            ))}
          </div>
          <div className="relative flex-1">
            <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="Search content..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-8 h-9"
            />
          </div>
        </div>

        {/* Selection controls */}
        {!selectedCollectionId && allContent.length > 0 && (
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <span>{selectedIds.length} selected</span>
            <span>&bull;</span>
            <button onClick={selectAll} className="hover:text-foreground transition-colors">
              Select all
            </button>
            <span>&bull;</span>
            <button onClick={clearSelection} className="hover:text-foreground transition-colors">
              Clear
            </button>
          </div>
        )}

        {/* Content list */}
        <div className="max-h-[45vh] overflow-y-auto rounded-md border bg-muted/10">
          {isLoading ? (
            <div className="flex items-center justify-center py-12 text-sm text-muted-foreground">
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Loading content...
            </div>
          ) : allContent.length === 0 ? (
            /* Empty state — hero CTA for first-time users */
            <div className="flex flex-col items-center justify-center py-12 px-6 gap-4 text-center">
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-primary/10">
                <FileText className="h-6 w-6 text-primary" />
              </div>
              <div className="space-y-1">
                <p className="text-sm font-semibold text-foreground">Add your first content</p>
                <p className="text-xs text-muted-foreground max-w-xs">
                  Chat works best with your videos and documents. Add something to get started.
                </p>
              </div>
              <div className="flex gap-3">
                <Button
                  variant="outline"
                  size="sm"
                  className="gap-2"
                  onClick={() => openAddPanel("url")}
                >
                  <Video className="h-4 w-4" />
                  Add video
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  className="gap-2"
                  onClick={() => openAddPanel("upload")}
                >
                  <Upload className="h-4 w-4" />
                  Upload doc
                </Button>
              </div>
            </div>
          ) : filteredContent.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 gap-2 text-center">
              <Search className="h-8 w-8 text-muted-foreground" />
              <p className="text-sm text-muted-foreground">No matching content</p>
            </div>
          ) : (
            <div className="divide-y">
              {filteredContent.map((item) => (
                <label
                  key={item.id}
                  className={cn(
                    "flex cursor-pointer items-center gap-3 px-4 py-3 hover:bg-muted/50 transition-colors",
                    selectedIds.includes(item.id) && "bg-primary/5"
                  )}
                >
                  <Checkbox
                    checked={selectedIds.includes(item.id)}
                    onCheckedChange={() => toggleItem(item.id)}
                    disabled={!!selectedCollectionId}
                  />
                  {item.type === "video" ? (
                    <Video className="h-4 w-4 flex-shrink-0 text-muted-foreground" />
                  ) : (
                    <FileText className="h-4 w-4 flex-shrink-0 text-muted-foreground" />
                  )}
                  <span className="flex-1 text-sm truncate">{item.title}</span>
                  <span className="text-xs text-muted-foreground whitespace-nowrap">
                    {item.type === "video" && item.duration_seconds
                      ? formatDuration(item.duration_seconds)
                      : item.type === "document" && item.page_count
                      ? `${item.page_count} pg`
                      : ""}
                  </span>
                </label>
              ))}
            </div>
          )}

          {/* Processing section */}
          {processingItems.length > 0 && (
            <div className="border-t pt-3 pb-3">
              <p className="text-xs font-medium text-muted-foreground mb-2 px-4">Processing...</p>
              {processingItems.map((item) => (
                <div key={item.id} className="flex items-center gap-3 px-4 py-2 opacity-50">
                  <Loader2 className="h-4 w-4 animate-spin flex-shrink-0" />
                  {item.type === "video" ? (
                    <Video className="h-4 w-4 flex-shrink-0 text-muted-foreground" />
                  ) : (
                    <FileText className="h-4 w-4 flex-shrink-0 text-muted-foreground" />
                  )}
                  <span className="text-sm truncate flex-1">{item.title}</span>
                  <Badge variant="outline" className="text-[10px]">
                    {item.status}
                  </Badge>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Start chat button */}
      <Button
        size="lg"
        className="gap-2"
        disabled={!hasSelection || isCreating}
        onClick={onStartChat}
      >
        {isCreating ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : (
          <MessageSquare className="h-4 w-4" />
        )}
        Start chatting
      </Button>

      {/* Inline AddContentPanel Sheet */}
      <AddContentPanel
        isOpen={addPanelOpen}
        onClose={() => setAddPanelOpen(false)}
        onSuccess={handleAddSuccess}
        defaultTab={addPanelTab}
      />
    </div>
  );
}
