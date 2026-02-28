"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
} from "@/components/ui/dialog";
import {
  Search,
  Link as LinkIcon,
  Loader2,
  Check,
  AlertCircle,
  Clock,
  Eye,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  X,
  Play,
  Upload,
} from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { discoveryApi } from "@/lib/api/discovery";
import { videosApi } from "@/lib/api/videos";
import { DocumentUploadZone } from "@/components/documents/DocumentUploadZone";
import {
  YouTubeSearchResult,
  YouTubeDurationFilter,
  YouTubePublishedFilter,
  YouTubeOrderFilter,
  YouTubeCategoryFilter,
} from "@/lib/types";
import { cn } from "@/lib/utils";

interface AddContentPanelProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess?: () => void;
  collectionId?: string;
  quotaRemaining?: number;
  defaultTab?: string;
}

export function AddContentPanel({
  isOpen,
  onClose,
  onSuccess,
  collectionId,
  quotaRemaining,
  defaultTab,
}: AddContentPanelProps) {
  const { toast } = useToast();
  const queryClient = useQueryClient();

  // URL tab state
  const [youtubeUrl, setYoutubeUrl] = useState("");

  // Search tab state
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<YouTubeSearchResult[]>([]);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [searchQuotaUsed, setSearchQuotaUsed] = useState(0);
  const [searchQuotaRemaining, setSearchQuotaRemaining] = useState<number | null>(null);
  const [hasSearched, setHasSearched] = useState(false);

  // Filter state
  const [durationFilter, setDurationFilter] = useState<YouTubeDurationFilter>(null);
  const [publishedFilter, setPublishedFilter] = useState<YouTubePublishedFilter>(null);
  const [orderFilter, setOrderFilter] = useState<YouTubeOrderFilter>("relevance");
  const [categoryFilter, setCategoryFilter] = useState<YouTubeCategoryFilter>(null);
  const [hideImported, setHideImported] = useState(false);

  // Preview modal state
  const [previewVideoId, setPreviewVideoId] = useState<string | null>(null);
  const [previewVideo, setPreviewVideo] = useState<YouTubeSearchResult | null>(null);

  // Input ref for auto-focus
  const searchInputRef = useRef<HTMLInputElement>(null);

  // Pagination state - supports both API (server-side) and yt-dlp (client-side) modes
  const [hasApiPagination, setHasApiPagination] = useState(false);
  const [nextPageToken, setNextPageToken] = useState<string | null>(null);
  const [prevPageToken, setPrevPageToken] = useState<string | null>(null);
  const [totalApiResults, setTotalApiResults] = useState<number | null>(null);
  const [currentPageNumber, setCurrentPageNumber] = useState(1);
  const [lastSearchQuery, setLastSearchQuery] = useState("");

  // For client-side pagination (yt-dlp mode)
  const resultsPerPage = 25;
  const clientSideTotalPages = Math.ceil(searchResults.length / resultsPerPage);
  const clientSidePaginatedResults = searchResults.slice(
    (currentPageNumber - 1) * resultsPerPage,
    currentPageNumber * resultsPerPage
  );

  // Use the appropriate results based on pagination mode
  const paginatedResults = hasApiPagination ? searchResults : clientSidePaginatedResults;
  // Apply client-side hide imported filter
  const displayedResults = hideImported
    ? paginatedResults.filter((r) => !r.already_imported)
    : paginatedResults;

  // Scroll refs
  const scrollAreaRef = useRef<HTMLDivElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const topRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  const scrollToTop = () => {
    topRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  // Auto-focus search input when panel opens
  useEffect(() => {
    if (isOpen) {
      // Small delay to ensure the panel is rendered
      const timer = setTimeout(() => {
        searchInputRef.current?.focus();
      }, 100);
      return () => clearTimeout(timer);
    }
  }, [isOpen]);

  // Reset state when panel closes
  const handleClose = useCallback(() => {
    setYoutubeUrl("");
    setSearchQuery("");
    setSearchResults([]);
    setSelectedIds(new Set());
    setHasSearched(false);
    setHasApiPagination(false);
    setNextPageToken(null);
    setPrevPageToken(null);
    setTotalApiResults(null);
    setCurrentPageNumber(1);
    setLastSearchQuery("");
    // Reset filters
    setDurationFilter(null);
    setPublishedFilter(null);
    setOrderFilter("relevance");
    setCategoryFilter(null);
    setHideImported(false);
    setPreviewVideoId(null);
    setPreviewVideo(null);
    onClose();
  }, [onClose]);

  // URL ingest mutation
  const ingestMutation = useMutation({
    mutationFn: videosApi.ingest,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["videos"] });
      queryClient.invalidateQueries({ queryKey: ["subscription-quota"] });
      toast({
        title: "Video queued",
        description: "The video has been added to the processing queue.",
      });
      handleClose();
      onSuccess?.();
    },
    onError: (error: unknown) => {
      const axiosError = error as any;
      const detail = axiosError?.response?.data?.detail;
      let message = "Failed to ingest video. Please check the URL.";

      if (typeof detail === "string") {
        message = detail;
      } else if (typeof detail === "object" && detail?.message) {
        message = detail.message;
      }

      toast({
        title: "Ingest failed",
        description: message,
        variant: "destructive",
      });
    },
  });

  // YouTube search mutation - handles both initial search and pagination
  const searchMutation = useMutation({
    mutationFn: async ({
      query,
      pageToken,
      filters,
    }: {
      query: string;
      pageToken?: string;
      filters?: {
        duration?: YouTubeDurationFilter;
        published_after?: YouTubePublishedFilter;
        order?: YouTubeOrderFilter;
        category?: YouTubeCategoryFilter;
      };
    }) => {
      // For API mode with pagination: fetch 25 per page
      // For yt-dlp mode (no pagination): fetch 100 and paginate client-side
      const maxResults = pageToken ? 25 : 100;
      return discoveryApi.search(query, maxResults, pageToken, filters);
    },
    onSuccess: (data, variables) => {
      setSearchResults(data.results);
      setSearchQuotaUsed(data.quota_used);
      setSearchQuotaRemaining(data.quota_remaining);
      setHasSearched(true);

      // Handle pagination state
      setHasApiPagination(data.has_api_pagination);
      setNextPageToken(data.next_page_token || null);
      setPrevPageToken(data.prev_page_token || null);
      setTotalApiResults(data.total_results || null);

      // Track query for page navigation
      setLastSearchQuery(variables.query);

      // Reset selections and page only on new search (no pageToken)
      if (!variables.pageToken) {
        setSelectedIds(new Set());
        setCurrentPageNumber(1);
      }
    },
    onError: (error: unknown) => {
      const axiosError = error as any;
      const detail = axiosError?.response?.data?.detail;
      let message = "Search failed. Please try again.";

      if (typeof detail === "string") {
        message = detail;
      } else if (typeof detail === "object" && detail?.message) {
        message = detail.message;
      }

      toast({
        title: "Search failed",
        description: message,
        variant: "destructive",
      });
    },
  });

  // Batch import mutation
  const importMutation = useMutation({
    mutationFn: async (youtubeIds: string[]) => {
      return discoveryApi.batchImport(youtubeIds, collectionId);
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["videos"] });
      queryClient.invalidateQueries({ queryKey: ["subscription-quota"] });

      if (data.imported > 0) {
        toast({
          title: "Videos imported",
          description: `${data.imported} video(s) added to processing queue.`,
        });
      }

      if (data.skipped && data.skipped > 0) {
        toast({
          title: "Some videos skipped",
          description: `${data.skipped} video(s) were already in your library.`,
        });
      }

      if (data.failed > 0) {
        toast({
          title: "Some imports failed",
          description: `${data.failed} video(s) could not be imported.`,
          variant: "destructive",
        });
      }

      handleClose();
      onSuccess?.();
    },
    onError: (error: unknown) => {
      const axiosError = error as any;
      const detail = axiosError?.response?.data?.detail;
      let message = "Import failed. Please try again.";

      if (typeof detail === "string") {
        message = detail;
      } else if (typeof detail === "object" && detail?.message) {
        message = detail.message;
      }

      toast({
        title: "Import failed",
        description: message,
        variant: "destructive",
      });
    },
  });

  const handleUrlSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!youtubeUrl.trim()) return;
    ingestMutation.mutate(youtubeUrl.trim());
  };

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;
    searchMutation.mutate({
      query: searchQuery.trim(),
      filters: {
        duration: durationFilter,
        published_after: publishedFilter,
        order: orderFilter,
        category: categoryFilter,
      },
    });
  };

  // Clear search query
  const handleClearSearch = () => {
    setSearchQuery("");
    setSearchResults([]);
    setHasSearched(false);
    setSelectedIds(new Set());
    setCurrentPageNumber(1);
    searchInputRef.current?.focus();
  };

  // Select all / deselect all
  const selectableResults = (hideImported
    ? displayedResults.filter((r) => !r.already_imported)
    : displayedResults.filter((r) => !r.already_imported)
  );

  const handleSelectAll = () => {
    const newSelected = new Set(selectedIds);
    for (const r of selectableResults) {
      if (newSelected.size >= MAX_IMPORT_BATCH) break;
      newSelected.add(r.id);
    }
    setSelectedIds(newSelected);
  };

  const handleDeselectAll = () => {
    const newSelected = new Set(selectedIds);
    selectableResults.forEach((r) => newSelected.delete(r.id));
    setSelectedIds(newSelected);
  };

  // Calculate estimated duration for selected videos
  const selectedDurationMinutes = searchResults
    .filter((r) => selectedIds.has(r.id) && r.duration_seconds)
    .reduce((sum, r) => sum + (r.duration_seconds || 0), 0) / 60;

  // Navigate to next/previous page (API mode)
  const handleNextPage = () => {
    if (hasApiPagination && nextPageToken) {
      searchMutation.mutate({
        query: lastSearchQuery,
        pageToken: nextPageToken,
        filters: {
          duration: durationFilter,
          published_after: publishedFilter,
          order: orderFilter,
          category: categoryFilter,
        },
      });
      setCurrentPageNumber((p) => p + 1);
      scrollToTop();
    } else if (!hasApiPagination) {
      // Client-side pagination
      setCurrentPageNumber((p) => Math.min(clientSideTotalPages, p + 1));
      scrollToTop();
    }
  };

  const handlePrevPage = () => {
    if (hasApiPagination && prevPageToken) {
      searchMutation.mutate({
        query: lastSearchQuery,
        pageToken: prevPageToken,
        filters: {
          duration: durationFilter,
          published_after: publishedFilter,
          order: orderFilter,
          category: categoryFilter,
        },
      });
      setCurrentPageNumber((p) => Math.max(1, p - 1));
      scrollToTop();
    } else if (!hasApiPagination) {
      // Client-side pagination
      setCurrentPageNumber((p) => Math.max(1, p - 1));
      scrollToTop();
    }
  };

  const MAX_IMPORT_BATCH = 10;

  const toggleSelection = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else if (next.size < MAX_IMPORT_BATCH) {
        next.add(id);
      }
      return next;
    });
  };

  const handleImportSelected = () => {
    const ids = Array.from(selectedIds);
    if (ids.length === 0) return;
    importMutation.mutate(ids);
  };

  const selectedCount = selectedIds.size;
  const importableResults = searchResults.filter((r) => !r.already_imported);
  const quotaWillExceed =
    quotaRemaining !== undefined && selectedCount > quotaRemaining;

  return (
    <Sheet open={isOpen} onOpenChange={(open) => !open && handleClose()}>
      <SheetContent side="right" className="w-full sm:max-w-2xl flex flex-col">
        <SheetHeader>
          <SheetTitle>Add content</SheetTitle>
          <SheetDescription>
            Import YouTube videos by URL or search for content to add.
          </SheetDescription>
        </SheetHeader>

        <Tabs defaultValue={defaultTab || "url"} className="flex-1 flex flex-col mt-4">
          <TabsList className="grid w-full grid-cols-3">
            <TabsTrigger value="url" className="gap-2">
              <LinkIcon className="h-4 w-4" />
              URL
            </TabsTrigger>
            <TabsTrigger value="search" className="gap-2">
              <Search className="h-4 w-4" />
              Search
            </TabsTrigger>
            <TabsTrigger value="upload" className="gap-2">
              <Upload className="h-4 w-4" />
              Upload
            </TabsTrigger>
          </TabsList>

          {/* URL Tab */}
          <TabsContent value="url" className="flex-1 space-y-4">
            <form onSubmit={handleUrlSubmit} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="youtube-url">YouTube URL</Label>
                <Input
                  id="youtube-url"
                  type="url"
                  placeholder="https://www.youtube.com/watch?v=..."
                  value={youtubeUrl}
                  onChange={(e) => setYoutubeUrl(e.target.value)}
                  disabled={ingestMutation.isPending}
                />
                <p className="text-xs text-muted-foreground">
                  Paste a YouTube video URL to start processing.
                </p>
              </div>

              {quotaRemaining !== undefined && quotaRemaining <= 0 && (
                <div className="flex items-center gap-2 rounded-md border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
                  <AlertCircle className="h-4 w-4 flex-shrink-0" />
                  <span>Video quota exceeded. Upgrade to add more videos.</span>
                </div>
              )}

              <Button
                type="submit"
                className="w-full gap-2"
                disabled={
                  ingestMutation.isPending ||
                  !youtubeUrl.trim() ||
                  (quotaRemaining !== undefined && quotaRemaining <= 0)
                }
              >
                {ingestMutation.isPending ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Processing...
                  </>
                ) : (
                  "Add video"
                )}
              </Button>
            </form>
          </TabsContent>

          {/* Search Tab */}
          <TabsContent value="search" className="flex-1 flex flex-col space-y-3">
            <form onSubmit={handleSearch} className="space-y-3">
              {/* Search input row */}
              <div className="flex gap-2">
                <div className="relative flex-1">
                  <Input
                    ref={searchInputRef}
                    type="text"
                    placeholder="Search YouTube..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    disabled={searchMutation.isPending}
                    className="pr-8"
                  />
                  {searchQuery && (
                    <button
                      type="button"
                      onClick={handleClearSearch}
                      className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                    >
                      <X className="h-4 w-4" />
                    </button>
                  )}
                </div>
                <Select value={orderFilter} onValueChange={(v) => setOrderFilter(v as YouTubeOrderFilter)}>
                  <SelectTrigger className="w-[130px]">
                    <SelectValue placeholder="Sort by" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="relevance">Relevance</SelectItem>
                    <SelectItem value="date">Newest</SelectItem>
                    <SelectItem value="viewCount">Most viewed</SelectItem>
                  </SelectContent>
                </Select>
                <Button
                  type="submit"
                  size="icon"
                  disabled={searchMutation.isPending || !searchQuery.trim()}
                >
                  {searchMutation.isPending ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Search className="h-4 w-4" />
                  )}
                </Button>
              </div>

              {/* Filter row */}
              <div className="flex flex-wrap items-center gap-2">
                <Select
                  value={durationFilter || "any"}
                  onValueChange={(v) => setDurationFilter(v === "any" ? null : v as YouTubeDurationFilter)}
                >
                  <SelectTrigger className="w-[100px] h-8 text-xs">
                    <SelectValue placeholder="Duration" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="any">Any length</SelectItem>
                    <SelectItem value="short">&lt; 4 min</SelectItem>
                    <SelectItem value="medium">4-20 min</SelectItem>
                    <SelectItem value="long">&gt; 20 min</SelectItem>
                  </SelectContent>
                </Select>

                <Select
                  value={publishedFilter || "any"}
                  onValueChange={(v) => setPublishedFilter(v === "any" ? null : v as YouTubePublishedFilter)}
                >
                  <SelectTrigger className="w-[100px] h-8 text-xs">
                    <SelectValue placeholder="Upload date" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="any">Any time</SelectItem>
                    <SelectItem value="week">Past week</SelectItem>
                    <SelectItem value="month">Past month</SelectItem>
                    <SelectItem value="year">Past year</SelectItem>
                  </SelectContent>
                </Select>

                <Select
                  value={categoryFilter || "any"}
                  onValueChange={(v) => setCategoryFilter(v === "any" ? null : v as YouTubeCategoryFilter)}
                >
                  <SelectTrigger className="w-[110px] h-8 text-xs">
                    <SelectValue placeholder="Type" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="any">Any type</SelectItem>
                    <SelectItem value="education">Education</SelectItem>
                    <SelectItem value="howto">How-to</SelectItem>
                    <SelectItem value="tech">Tech</SelectItem>
                    <SelectItem value="entertainment">Entertainment</SelectItem>
                  </SelectContent>
                </Select>

                <div className="flex items-center gap-2 ml-auto">
                  <Checkbox
                    id="hide-imported"
                    checked={hideImported}
                    onCheckedChange={(checked) => setHideImported(!!checked)}
                  />
                  <label
                    htmlFor="hide-imported"
                    className="text-xs text-muted-foreground cursor-pointer select-none"
                  >
                    Hide imported
                  </label>
                </div>
              </div>

              {searchQuotaRemaining !== null && (
                <p className="text-xs text-muted-foreground">
                  {searchQuotaRemaining} searches remaining today
                </p>
              )}
            </form>

            {/* Select All / Deselect All row */}
            {hasSearched && displayedResults.length > 0 && (
              <div className="flex items-center justify-between py-2 border-b">
                <div className="flex gap-2">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={handleSelectAll}
                    disabled={selectableResults.length === 0}
                    className="h-7 text-xs"
                  >
                    Select all
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={handleDeselectAll}
                    disabled={selectedCount === 0}
                    className="h-7 text-xs"
                  >
                    Deselect all
                  </Button>
                </div>
                <span className="text-xs text-muted-foreground">
                  {displayedResults.length} result{displayedResults.length !== 1 ? "s" : ""}
                </span>
              </div>
            )}

            {/* Search Results */}
            <div className="relative flex-1 min-h-0 -mx-6">
              <ScrollArea className="h-full max-h-[55vh] px-6">
                <div ref={topRef} />
                {searchMutation.isPending ? (
                  <div className="space-y-3 py-2">
                    {[1, 2, 3].map((i) => (
                      <div key={i} className="flex gap-3 p-3 rounded-lg border">
                        <Skeleton className="w-32 h-20 rounded-md flex-shrink-0" />
                        <div className="flex-1 space-y-2">
                          <Skeleton className="h-4 w-3/4" />
                          <Skeleton className="h-3 w-1/2" />
                          <Skeleton className="h-3 w-1/4" />
                        </div>
                      </div>
                    ))}
                  </div>
                ) : searchResults.length > 0 ? (
                  <div className="space-y-2 py-2 pb-4">
                    {displayedResults.map((result) => (
                      <SearchResultItem
                        key={result.id}
                        result={result}
                        isSelected={selectedIds.has(result.id)}
                        onToggle={() => toggleSelection(result.id)}
                        onPreview={() => {
                          setPreviewVideoId(result.id);
                          setPreviewVideo(result);
                        }}
                      />
                    ))}
                  </div>
                ) : hasSearched ? (
                  <div className="text-center py-8 text-muted-foreground">
                    <Search className="h-12 w-12 mx-auto mb-2 opacity-50" />
                    <p>No results found for &quot;{lastSearchQuery}&quot;</p>
                    <p className="text-xs">Try different keywords or adjust filters</p>
                  </div>
                ) : (
                  <div className="text-center py-8 text-muted-foreground">
                    <Search className="h-12 w-12 mx-auto mb-2 opacity-50" />
                    <p>Search YouTube to find videos</p>
                    <p className="text-xs">Results will appear here</p>
                  </div>
                )}
                <div ref={bottomRef} />
              </ScrollArea>
            </div>

            {/* Pagination Controls */}
            {(hasApiPagination || searchResults.length > resultsPerPage) && hasSearched && (
              <div className="flex items-center justify-between py-3 border-t">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handlePrevPage}
                  disabled={
                    searchMutation.isPending ||
                    (hasApiPagination ? !prevPageToken : currentPageNumber === 1)
                  }
                  className="gap-1"
                >
                  <ChevronLeft className="h-4 w-4" />
                  Previous
                </Button>
                <span className="text-sm text-muted-foreground">
                  {hasApiPagination ? (
                    <>
                      Page {currentPageNumber}
                      {totalApiResults && ` (${totalApiResults.toLocaleString()} total)`}
                    </>
                  ) : (
                    <>
                      Page {currentPageNumber} of {clientSideTotalPages} ({searchResults.length} results)
                    </>
                  )}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleNextPage}
                  disabled={
                    searchMutation.isPending ||
                    (hasApiPagination ? !nextPageToken : currentPageNumber === clientSideTotalPages)
                  }
                  className="gap-1"
                >
                  Next
                  <ChevronRight className="h-4 w-4" />
                </Button>
              </div>
            )}

            {/* Selection Footer */}
            {selectedCount > 0 && (
              <div className="sticky bottom-0 -mx-6 px-6 py-4 bg-background border-t space-y-2">
                <div className="flex items-center justify-between text-sm">
                  <span>
                    {selectedCount}/{MAX_IMPORT_BATCH} video{selectedCount !== 1 ? "s" : ""} selected
                    {selectedDurationMinutes > 0 && (
                      <span className="text-muted-foreground ml-1">
                        (~{Math.round(selectedDurationMinutes)} min)
                      </span>
                    )}
                  </span>
                </div>

                {selectedCount >= MAX_IMPORT_BATCH && (
                  <div className="flex items-center gap-2 text-amber-600 text-xs">
                    <AlertCircle className="h-3 w-3" />
                    <span>Maximum {MAX_IMPORT_BATCH} videos per import. Deselect some to add others.</span>
                  </div>
                )}

                {quotaWillExceed && (
                  <div className="flex items-center gap-2 text-destructive text-xs">
                    <AlertCircle className="h-3 w-3" />
                    <span>Exceeds monthly quota ({quotaRemaining} remaining)</span>
                  </div>
                )}

                <Button
                  onClick={handleImportSelected}
                  className="w-full gap-2"
                  disabled={importMutation.isPending || quotaWillExceed}
                >
                  {importMutation.isPending ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Importing...
                    </>
                  ) : (
                    <>
                      <Check className="h-4 w-4" />
                      Import {selectedCount} video{selectedCount !== 1 ? "s" : ""}
                    </>
                  )}
                </Button>
              </div>
            )}
          </TabsContent>

          {/* Upload Tab */}
          <TabsContent value="upload" className="flex-1 space-y-4">
            <div className="space-y-2">
              <p className="text-sm text-muted-foreground">
                Upload documents (PDF, Word, PowerPoint, Excel, etc.) for RAG processing.
              </p>
              <DocumentUploadZone
                onUploadComplete={() => onSuccess?.()}
              />
            </div>
          </TabsContent>
        </Tabs>

        {/* Video Preview Modal */}
        <Dialog open={!!previewVideoId} onOpenChange={(open) => !open && setPreviewVideoId(null)}>
          <DialogContent className="max-w-3xl p-0 overflow-hidden">
            <div className="aspect-video bg-black">
              {previewVideoId && (
                <iframe
                  src={`https://www.youtube.com/embed/${previewVideoId}?autoplay=1`}
                  className="w-full h-full"
                  allow="autoplay; encrypted-media"
                  allowFullScreen
                />
              )}
            </div>
            {previewVideo && (
              <div className="p-4 space-y-3">
                <h3 className="font-medium line-clamp-2">{previewVideo.title}</h3>
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <span>{previewVideo.channel_name}</span>
                  {previewVideo.view_count && (
                    <>
                      <span>•</span>
                      <span>{formatViewCount(previewVideo.view_count)}</span>
                    </>
                  )}
                  {previewVideo.duration_seconds && (
                    <>
                      <span>•</span>
                      <span>{formatDuration(previewVideo.duration_seconds)}</span>
                    </>
                  )}
                </div>
                {previewVideo.description && (
                  <p className="text-sm text-muted-foreground line-clamp-3">
                    {previewVideo.description}
                  </p>
                )}
                <div className="flex gap-2 pt-2">
                  {previewVideo.already_imported ? (
                    <Button disabled variant="secondary" className="gap-2">
                      <CheckCircle2 className="h-4 w-4" />
                      Already imported
                    </Button>
                  ) : (
                    <Button
                      onClick={() => {
                        toggleSelection(previewVideoId!);
                        setPreviewVideoId(null);
                      }}
                      className="gap-2"
                    >
                      {selectedIds.has(previewVideoId!) ? (
                        <>
                          <Check className="h-4 w-4" />
                          Remove from selection
                        </>
                      ) : (
                        <>
                          <Check className="h-4 w-4" />
                          Add to selection
                        </>
                      )}
                    </Button>
                  )}
                </div>
              </div>
            )}
          </DialogContent>
        </Dialog>
      </SheetContent>
    </Sheet>
  );
}

interface SearchResultItemProps {
  result: YouTubeSearchResult;
  isSelected: boolean;
  onToggle: () => void;
  onPreview: () => void;
}

function SearchResultItem({ result, isSelected, onToggle, onPreview }: SearchResultItemProps) {
  const isImported = result.already_imported;

  return (
    <div
      className={cn(
        "flex gap-3 p-3 rounded-lg border transition-colors",
        isImported
          ? "opacity-60 bg-muted/30"
          : isSelected
          ? "border-primary bg-primary/5"
          : "hover:bg-muted/50"
      )}
    >
      {/* Checkbox */}
      <div className="flex items-start pt-1">
        <Checkbox
          checked={isSelected}
          onCheckedChange={() => !isImported && onToggle()}
          disabled={isImported}
          className="data-[state=checked]:bg-primary cursor-pointer"
        />
      </div>

      {/* Thumbnail - click opens preview */}
      <div
        className={cn(
          "relative w-32 h-20 rounded-md overflow-hidden flex-shrink-0 bg-muted group",
          !isImported && "cursor-pointer"
        )}
        onClick={() => !isImported && onPreview()}
      >
        {result.thumbnail_url ? (
          <img
            src={result.thumbnail_url}
            alt={result.title}
            className="w-full h-full object-cover"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            <Search className="h-6 w-6 text-muted-foreground" />
          </div>
        )}
        {/* Play button overlay on hover */}
        {!isImported && (
          <div className="absolute inset-0 flex items-center justify-center bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity">
            <Play className="h-8 w-8 text-white fill-white" />
          </div>
        )}
        {/* Duration overlay */}
        {result.duration_seconds && (
          <div className="absolute bottom-1 right-1 px-1 py-0.5 bg-black/80 text-white text-xs rounded">
            {formatDuration(result.duration_seconds)}
          </div>
        )}
      </div>

      {/* Content - click toggles selection */}
      <div
        className={cn(
          "flex-1 min-w-0 space-y-1",
          !isImported && "cursor-pointer"
        )}
        onClick={() => !isImported && onToggle()}
      >
        <h4 className="font-medium text-sm line-clamp-2 leading-tight">
          {result.title}
        </h4>
        <p className="text-xs text-muted-foreground truncate">
          {result.channel_name}
        </p>
        {/* Description preview */}
        {result.description && (
          <p className="text-xs text-muted-foreground line-clamp-2">
            {result.description}
          </p>
        )}
        <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
          {result.view_count && (
            <span className="flex items-center gap-1">
              <Eye className="h-3 w-3" />
              {formatViewCount(result.view_count)}
            </span>
          )}
          {result.published_at && formatRelativeDate(result.published_at) && (
            <span className="flex items-center gap-1">
              <Clock className="h-3 w-3" />
              {formatRelativeDate(result.published_at)}
            </span>
          )}
        </div>
        {isImported && (
          <Badge variant="secondary" className="text-xs gap-1">
            <CheckCircle2 className="h-3 w-3" />
            Already imported
          </Badge>
        )}
      </div>
    </div>
  );
}

function formatDuration(seconds: number | undefined): string {
  if (!seconds) return "";
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = seconds % 60;
  if (hours > 0) {
    return `${hours}:${minutes.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
  }
  return `${minutes}:${secs.toString().padStart(2, "0")}`;
}

function formatViewCount(count: number): string {
  if (count >= 1_000_000) {
    return `${(count / 1_000_000).toFixed(1)}M views`;
  }
  if (count >= 1_000) {
    return `${(count / 1_000).toFixed(1)}K views`;
  }
  return `${count} views`;
}

function formatRelativeDate(dateString: string | null | undefined): string {
  if (!dateString) return "";

  const date = new Date(dateString);
  if (isNaN(date.getTime())) return "";

  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

  if (diffDays < 0) return "";
  if (diffDays === 0) return "Today";
  if (diffDays === 1) return "Yesterday";
  if (diffDays < 7) return `${diffDays} days ago`;
  if (diffDays < 30) return `${Math.floor(diffDays / 7)} weeks ago`;
  if (diffDays < 365) return `${Math.floor(diffDays / 30)} months ago`;
  return `${Math.floor(diffDays / 365)} years ago`;
}
