"use client";

import { Suspense, useState, useCallback, useEffect, useMemo } from "react";
import { useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient, keepPreviousData } from "@tanstack/react-query";
import Link from "next/link";
import { MainLayout } from "@/components/layout/MainLayout";
import { useSetBreadcrumb } from "@/contexts/BreadcrumbContext";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Table,
  TableBody,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
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
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  TooltipProvider,
} from "@/components/ui/tooltip";
import {
  FileText,
  FolderPlus,
  Plus,
  Search,
  Loader2,
  Trash2,
  Upload,
} from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { useAuthState } from "@/lib/auth";
import { contentApi } from "@/lib/api/content";
import { DocumentRow } from "@/components/documents/DocumentRow";
import { DocumentUploadZone } from "@/components/documents/DocumentUploadZone";
import { AddToCollectionModal } from "@/components/videos/AddToCollectionModal";
import type { ContentItem, ContentListResponse } from "@/lib/types";
import { formatFileSize } from "@/lib/content-type-utils";
import { usePaginationParams } from "@/hooks/usePaginationParams";
import { PaginationBar } from "@/components/shared/PaginationBar";

export default function DocumentsPage() {
  return (
    <Suspense>
      <DocumentsPageContent />
    </Suspense>
  );
}

function DocumentsPageContent() {
  const router = useRouter();
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const authState = useAuthState();
  const canFetch = authState.isAuthenticated;

  // Pagination
  const { page, pageSize, skip, setPage, setPageSize } = usePaginationParams();

  // Filters
  const [searchQuery, setSearchQuery] = useState("");
  const [typeFilter, setTypeFilter] = useState<string>("all");
  const [statusFilter, setStatusFilter] = useState<string>("all");

  // Selection
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  // Dialogs
  const [showUpload, setShowUpload] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);
  const [cancelTarget, setCancelTarget] = useState<string | null>(null);
  const [showBulkDelete, setShowBulkDelete] = useState(false);
  const [addToCollectionIds, setAddToCollectionIds] = useState<string[]>([]);

  // Fetch documents
  const { data, isLoading, isFetching, error } = useQuery<ContentListResponse>({
    queryKey: [
      "documents",
      { page, pageSize },
      searchQuery,
      typeFilter,
      statusFilter,
    ],
    queryFn: () =>
      contentApi.list(
        skip,
        pageSize,
        typeFilter !== "all" ? typeFilter : undefined,
        statusFilter !== "all" ? statusFilter : undefined,
        searchQuery || undefined
      ),
    enabled: canFetch,
    placeholderData: keepPreviousData,
    refetchInterval: (query) => {
      const items = query.state.data?.items;
      if (!items || items.length === 0) return 30000;
      const hasProcessing = items.some(
        (d) => !["completed", "failed", "canceled"].includes(d.status)
      );
      return hasProcessing ? 5000 : 30000;
    },
  });

  // Fetch counts (separate from filtered list)
  const { data: counts } = useQuery({
    queryKey: ["document-counts"],
    queryFn: () => contentApi.getCounts(),
    enabled: canFetch,
    refetchInterval: (query) => {
      const c = query.state.data;
      return c && c.processing > 0 ? 5000 : 30000;
    },
  });

  const documents = data?.items || [];
  const totalCount = data?.total || 0;

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: (id: string) => contentApi.delete(id),
    onSuccess: () => {
      toast({ title: "Document deleted" });
      queryClient.invalidateQueries({ queryKey: ["documents"] });
      queryClient.invalidateQueries({ queryKey: ["document-counts"] });
      setDeleteTarget(null);
    },
    onError: (err: any) => {
      toast({
        title: "Delete failed",
        description: err?.response?.data?.detail || err.message,
        variant: "destructive",
      });
    },
  });

  const bulkDeleteMutation = useMutation({
    mutationFn: (ids: string[]) => contentApi.deleteBulk(ids),
    onSuccess: (result) => {
      toast({
        title: `Deleted ${result.deleted_count} document(s)`,
        description: result.message,
      });
      setSelectedIds(new Set());
      setShowBulkDelete(false);
      queryClient.invalidateQueries({ queryKey: ["documents"] });
      queryClient.invalidateQueries({ queryKey: ["document-counts"] });
    },
    onError: (err: any) => {
      toast({
        title: "Bulk delete failed",
        description: err?.response?.data?.detail || err.message,
        variant: "destructive",
      });
    },
  });

  // Cancel mutation
  const cancelMutation = useMutation({
    mutationFn: (id: string) => contentApi.cancel(id),
    onSuccess: () => {
      toast({ title: "Processing canceled" });
      queryClient.invalidateQueries({ queryKey: ["documents"] });
      queryClient.invalidateQueries({ queryKey: ["document-counts"] });
      setCancelTarget(null);
    },
    onError: (err: any) => {
      toast({
        title: "Cancel failed",
        description: err?.response?.data?.detail || err.message,
        variant: "destructive",
      });
    },
  });

  // Clear selection when page changes
  useEffect(() => {
    setSelectedIds(new Set());
  }, [page, pageSize]);

  // Selection handlers
  const toggleSelect = useCallback((id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const selectAll = useCallback(() => {
    if (selectedIds.size === documents.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(documents.map((d) => d.id)));
    }
  }, [documents, selectedIds.size]);

  // Stats
  const completedCount = documents.filter(
    (d) => d.status === "completed"
  ).length;
  const processingCount = documents.filter(
    (d) => !["completed", "failed", "canceled"].includes(d.status)
  ).length;
  const totalSizeMB = documents.reduce(
    (sum, d) => sum + (d.storage_total_mb || 0),
    0
  );

  // Breadcrumb
  const breadcrumbDetail = useMemo(() => {
    if (documents.length === 0) return undefined;
    if (processingCount > 0) return `${processingCount} processing`;
    return `${totalCount} document${totalCount !== 1 ? "s" : ""}`;
  }, [documents.length, processingCount, totalCount]);

  useSetBreadcrumb("documents", breadcrumbDetail);

  // Unauthenticated state
  if (!canFetch) {
    return (
      <MainLayout>
        <Card>
          <CardHeader className="text-center">
            <CardTitle>Sign in to view documents</CardTitle>
            <CardDescription>Upload and chat with your documents after signing in.</CardDescription>
          </CardHeader>
          <CardContent className="flex justify-center pb-8">
            <div className="flex flex-col gap-2 sm:flex-row">
              <Button asChild>
                <Link href="/sign-up">Create account</Link>
              </Button>
              <Button asChild variant="outline">
                <Link href="/login">Sign in</Link>
              </Button>
            </div>
          </CardContent>
        </Card>
      </MainLayout>
    );
  }

  return (
    <MainLayout>
    <TooltipProvider>
      <div className="space-y-6">
        {/* Page header */}
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <p className="text-sm font-medium text-muted-foreground">
              Document library
            </p>
            <h1 className="text-3xl font-semibold tracking-tight">Documents</h1>
            <p className="text-sm text-muted-foreground">
              Upload and manage PDF, Word, and other document files for RAG
            </p>
            {totalCount > 0 && (
              <div className="mt-1 flex items-center gap-2 text-xs text-muted-foreground">
                <span>{totalCount} document{totalCount !== 1 ? "s" : ""}</span>
                {processingCount > 0 && (
                  <>
                    <span>&bull;</span>
                    <span>{processingCount} processing</span>
                  </>
                )}
                {totalSizeMB > 0 && (
                  <>
                    <span>&bull;</span>
                    <span>{totalSizeMB.toFixed(1)} MB</span>
                  </>
                )}
              </div>
            )}
          </div>
          <Button onClick={() => setShowUpload(true)}>
            <Plus className="mr-2 h-4 w-4" />
            Upload documents
          </Button>
        </div>

        {/* Document table card */}
        <Card>
          <CardHeader className="pb-3">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              {/* Left: selection info or filter bar */}
              <div className="flex items-center gap-3">
                {selectedIds.size > 0 ? (
                  <>
                    <span className="text-sm text-muted-foreground">
                      {selectedIds.size} selected
                    </span>
                    <Button
                      variant="outline"
                      size="sm"
                      className="gap-1"
                      onClick={() => setAddToCollectionIds(Array.from(selectedIds))}
                    >
                      <FolderPlus className="h-3.5 w-3.5" />
                      Add to collection
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      className="text-destructive"
                      onClick={() => setShowBulkDelete(true)}
                    >
                      <Trash2 className="mr-1 h-3 w-3" />
                      Delete
                    </Button>
                  </>
                ) : (
                  <div className="relative">
                    <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                    <Input
                      placeholder="Search documents..."
                      value={searchQuery}
                      onChange={(e) => { setSearchQuery(e.target.value); setPage(1); }}
                      className="h-9 w-[200px] pl-8 sm:w-[250px]"
                    />
                  </div>
                )}
              </div>

              {/* Right: filters */}
              <div className="flex items-center gap-2">
                <Select value={typeFilter} onValueChange={(v) => { setTypeFilter(v); setPage(1); }}>
                  <SelectTrigger className="h-9 w-[120px]">
                    <SelectValue placeholder="Type" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All types</SelectItem>
                    <SelectItem value="pdf">PDF</SelectItem>
                    <SelectItem value="docx">Word</SelectItem>
                    <SelectItem value="pptx">PowerPoint</SelectItem>
                    <SelectItem value="xlsx">Excel</SelectItem>
                    <SelectItem value="txt">Text</SelectItem>
                    <SelectItem value="md">Markdown</SelectItem>
                    <SelectItem value="html">HTML</SelectItem>
                    <SelectItem value="epub">EPUB</SelectItem>
                    <SelectItem value="csv">CSV</SelectItem>
                  </SelectContent>
                </Select>
                <Select value={statusFilter} onValueChange={(v) => { setStatusFilter(v); setPage(1); }}>
                  <SelectTrigger className="h-9 w-[160px]">
                    <SelectValue placeholder="Status" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">
                      All statuses{counts ? ` (${counts.total})` : ""}
                    </SelectItem>
                    <SelectItem value="completed">
                      Completed{counts ? ` (${counts.completed})` : ""}
                    </SelectItem>
                    <SelectItem value="processing">
                      Processing{counts ? ` (${counts.processing})` : ""}
                    </SelectItem>
                    <SelectItem value="failed">
                      Failed{counts ? ` (${counts.failed})` : ""}
                    </SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
          </CardHeader>
          <CardContent className="pt-0">
            {/* Loading state */}
            {isLoading && (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                <span className="ml-2 text-sm text-muted-foreground">
                  Loading documents...
                </span>
              </div>
            )}

            {/* Error state */}
            {error && (
              <div className="py-12 text-center text-sm text-destructive">
                Failed to load documents. Please try again.
              </div>
            )}

            {/* Empty state */}
            {!isLoading && !error && documents.length === 0 && (
              (() => {
                const hasFilters = searchQuery || typeFilter !== "all" || statusFilter !== "all";
                return (
                  <div className="flex flex-col items-center justify-center py-12">
                    <div className="flex h-16 w-16 items-center justify-center rounded-full bg-muted">
                      {hasFilters ? (
                        <Search className="h-8 w-8 text-muted-foreground" />
                      ) : (
                        <FileText className="h-8 w-8 text-muted-foreground" />
                      )}
                    </div>
                    {hasFilters ? (
                      <>
                        <h3 className="mt-4 text-lg font-medium">No matching documents</h3>
                        <p className="mt-1 text-sm text-muted-foreground">
                          Try adjusting your filters or search query
                        </p>
                        <Button
                          className="mt-4"
                          variant="outline"
                          onClick={() => {
                            setSearchQuery("");
                            setTypeFilter("all");
                            setStatusFilter("all");
                            setPage(1);
                          }}
                        >
                          Clear filters
                        </Button>
                      </>
                    ) : (
                      <>
                        <h3 className="mt-4 text-lg font-medium">No documents yet</h3>
                        <p className="mt-1 text-sm text-muted-foreground">
                          Upload your first document to start chatting with it
                        </p>
                        <Button
                          className="mt-4"
                          onClick={() => setShowUpload(true)}
                        >
                          <Upload className="mr-2 h-4 w-4" />
                          Upload documents
                        </Button>
                      </>
                    )}
                  </div>
                );
              })()
            )}

            {/* Document table */}
            {!isLoading && !error && documents.length > 0 && (
              <Table className={`transition-opacity ${isFetching && !isLoading ? "opacity-60" : ""}`}>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-12">
                      <Checkbox
                        checked={
                          selectedIds.size === documents.length &&
                          documents.length > 0
                        }
                        onCheckedChange={selectAll}
                      />
                    </TableHead>
                    <TableHead className="w-[40%]">Document</TableHead>
                    <TableHead className="w-[12%]">Type</TableHead>
                    <TableHead className="w-[15%]">Status</TableHead>
                    <TableHead className="w-[10%]">Size</TableHead>
                    <TableHead className="w-[23%] text-right">
                      Actions
                    </TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {documents.map((doc) => (
                    <DocumentRow
                      key={doc.id}
                      document={doc}
                      isSelected={selectedIds.has(doc.id)}
                      onSelect={toggleSelect}
                      onDelete={(id) => setDeleteTarget(id)}
                      onCancel={(id) => setCancelTarget(id)}
                      onView={(id) => router.push(`/documents/${id}`)}
                      onAddToCollection={(id) => setAddToCollectionIds([id])}
                    />
                  ))}
                </TableBody>
              </Table>
            )}

            {!isLoading && !error && (data?.total ?? 0) > 0 && (
              <div className="border-t">
                <PaginationBar
                  page={page}
                  pageSize={pageSize}
                  total={data?.total ?? 0}
                  onPageChange={setPage}
                  onPageSizeChange={setPageSize}
                  isLoading={isFetching}
                  itemLabel="documents"
                />
              </div>
            )}
          </CardContent>
        </Card>

        {/* Upload dialog */}
        <Dialog open={showUpload} onOpenChange={setShowUpload}>
          <DialogContent className="sm:max-w-lg">
            <DialogHeader>
              <DialogTitle>Upload documents</DialogTitle>
              <DialogDescription>
                Upload PDF, Word, PowerPoint, Excel, and other document files.
                They will be processed and indexed for RAG conversations.
              </DialogDescription>
            </DialogHeader>
            <DocumentUploadZone
              onUploadComplete={() => {
                queryClient.invalidateQueries({ queryKey: ["documents"] });
              }}
            />
          </DialogContent>
        </Dialog>

        {/* Delete confirmation */}
        <Dialog
          open={deleteTarget !== null}
          onOpenChange={(open) => {
            if (!open) setDeleteTarget(null);
          }}
        >
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Delete document</DialogTitle>
              <DialogDescription>
                This will permanently delete the document and its indexed data.
                This action cannot be undone.
              </DialogDescription>
            </DialogHeader>
            <DialogFooter>
              <Button
                variant="outline"
                onClick={() => setDeleteTarget(null)}
              >
                Cancel
              </Button>
              <Button
                variant="destructive"
                disabled={deleteMutation.isPending}
                onClick={() => {
                  if (deleteTarget) deleteMutation.mutate(deleteTarget);
                }}
              >
                {deleteMutation.isPending && (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                )}
                Delete
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Cancel confirmation */}
        <Dialog
          open={cancelTarget !== null}
          onOpenChange={(open) => {
            if (!open) setCancelTarget(null);
          }}
        >
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Cancel processing</DialogTitle>
              <DialogDescription>
                The document will be saved with canceled status. You can
                reprocess it later.
              </DialogDescription>
            </DialogHeader>
            <DialogFooter>
              <Button
                variant="outline"
                onClick={() => setCancelTarget(null)}
              >
                Keep processing
              </Button>
              <Button
                variant="destructive"
                disabled={cancelMutation.isPending}
                onClick={() => {
                  if (cancelTarget) cancelMutation.mutate(cancelTarget);
                }}
              >
                {cancelMutation.isPending && (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                )}
                Cancel processing
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Add to collection modal */}
        {addToCollectionIds.length > 0 && (
          <AddToCollectionModal
            videoIds={addToCollectionIds}
            videoTitle={
              addToCollectionIds.length === 1
                ? documents.find((d) => d.id === addToCollectionIds[0])?.title
                : undefined
            }
            onClose={() => setAddToCollectionIds([])}
          />
        )}

        {/* Bulk delete confirmation */}
        <Dialog open={showBulkDelete} onOpenChange={setShowBulkDelete}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Delete {selectedIds.size} documents</DialogTitle>
              <DialogDescription>
                This will permanently delete the selected documents and their
                indexed data. This action cannot be undone.
              </DialogDescription>
            </DialogHeader>
            <DialogFooter>
              <Button
                variant="outline"
                onClick={() => setShowBulkDelete(false)}
              >
                Cancel
              </Button>
              <Button
                variant="destructive"
                disabled={bulkDeleteMutation.isPending}
                onClick={() =>
                  bulkDeleteMutation.mutate(Array.from(selectedIds))
                }
              >
                {bulkDeleteMutation.isPending && (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                )}
                Delete {selectedIds.size} documents
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </TooltipProvider>
    </MainLayout>
  );
}
