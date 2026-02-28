"use client";

import { Suspense, useState } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { formatDistanceToNow } from "date-fns";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  ArrowLeft,
  Download,
  FolderPlus,
  Trash2,
  Loader2,
  MessageSquare,
  FileText,
  Maximize2,
  Minimize2,
} from "lucide-react";
import { MainLayout } from "@/components/layout/MainLayout";
import { AddToCollectionModal } from "@/components/videos/AddToCollectionModal";
import { useSetBreadcrumb } from "@/contexts/BreadcrumbContext";
import { useToast } from "@/hooks/use-toast";
import { contentApi } from "@/lib/api/content";
import {
  getContentTypeConfig,
  getContentTypeLabel,
  getContentTypeBadgeClass,
  formatFileSize,
} from "@/lib/content-type-utils";
import type { ContentItem } from "@/lib/types";
import { cn } from "@/lib/utils";

function DocumentDetailPageInner() {
  const params = useParams();
  const router = useRouter();
  const searchParams = useSearchParams();
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const id = params.id as string;
  const page = searchParams.get("page");
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [showAddToCollection, setShowAddToCollection] = useState(false);
  const [isFullPage, setIsFullPage] = useState(false);

  const { data: document, isLoading, error } = useQuery<ContentItem>({
    queryKey: ["document", id],
    queryFn: () => contentApi.get(id),
    enabled: !!id,
    refetchInterval: (query) => {
      const doc = query.state.data;
      if (doc && !["completed", "failed", "canceled"].includes(doc.status)) {
        return 5000; // Poll while processing
      }
      return false;
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () => contentApi.delete(id),
    onSuccess: () => {
      toast({ title: "Document deleted" });
      queryClient.invalidateQueries({ queryKey: ["documents"] });
      router.push("/documents");
    },
    onError: (err: any) => {
      toast({
        title: "Delete failed",
        description: err?.response?.data?.detail || err.message,
        variant: "destructive",
      });
    },
  });

  useSetBreadcrumb("documents", document?.title);

  if (isLoading) {
    return (
      <MainLayout>
        <div className="flex items-center justify-center py-20">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          <span className="ml-2 text-sm text-muted-foreground">
            Loading document...
          </span>
        </div>
      </MainLayout>
    );
  }

  if (error || !document) {
    return (
      <MainLayout>
        <div className="space-y-4">
          <Button variant="ghost" onClick={() => router.push("/documents")}>
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to documents
          </Button>
          <div className="py-12 text-center text-sm text-destructive">
            Document not found or failed to load.
          </div>
        </div>
      </MainLayout>
    );
  }

  const config = getContentTypeConfig(document.content_type);
  const TypeIcon = config.icon;

  return (
    <MainLayout>
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Button
          variant="ghost"
          size="icon"
          onClick={() => router.push("/documents")}
        >
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <h1 className="truncate text-xl font-bold">{document.title}</h1>
            <Badge
              variant="outline"
              className={cn("shrink-0", getContentTypeBadgeClass(document.content_type))}
            >
              {getContentTypeLabel(document.content_type)}
            </Badge>
          </div>
          {document.original_filename && (
            <p className="text-sm text-muted-foreground">
              {document.original_filename}
            </p>
          )}
        </div>
      </div>

      {/* Fullscreen PDF overlay */}
      {isFullPage && document.status === "completed" && (
        <div className="fixed inset-0 z-50 bg-background">
          <div className="absolute right-4 top-3 z-10 flex items-center gap-2">
            <span className="text-sm text-muted-foreground truncate max-w-xs">
              {document.title}
            </span>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setIsFullPage(false)}
            >
              <Minimize2 className="mr-2 h-4 w-4" />
              Exit full page
            </Button>
          </div>
          <iframe
            src={`${contentApi.getFileUrl(id)}#page=${page || 1}`}
            className="h-full w-full border-0"
            title={document.title}
          />
        </div>
      )}

      {/* Two-panel layout */}
      <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
        {/* Left: Document viewer */}
        <Card>
          <CardContent className="relative p-0 overflow-hidden rounded-lg">
            {document.status === "completed" && (
              <Button
                variant="ghost"
                size="icon"
                className="absolute right-2 top-2 z-10 h-8 w-8 bg-background/80 backdrop-blur-sm hover:bg-background"
                onClick={() => setIsFullPage(true)}
                title="Full page view"
              >
                <Maximize2 className="h-4 w-4" />
              </Button>
            )}
            {document.status === "completed" ? (
              <iframe
                src={`${contentApi.getFileUrl(id)}#page=${page || 1}`}
                className="w-full border-0 rounded-lg"
                style={{ minHeight: "700px", height: "calc(100vh - 200px)" }}
                title={document.title}
              />
            ) : document.status === "failed" ? (
              <div className="flex min-h-[500px] items-center justify-center">
                <div className="text-center">
                  <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-destructive/10">
                    <FileText className="h-8 w-8 text-destructive" />
                  </div>
                  <h3 className="mt-4 text-lg font-medium">Processing failed</h3>
                  <p className="mt-1 text-sm text-muted-foreground">
                    {document.error_message || "An error occurred during processing."}
                  </p>
                </div>
              </div>
            ) : (
              <div className="flex min-h-[500px] items-center justify-center">
                <div className="text-center">
                  <Loader2 className="mx-auto h-8 w-8 animate-spin text-muted-foreground" />
                  <p className="mt-4 text-sm text-muted-foreground">
                    Processing... {Math.round(document.progress_percent || 0)}%
                  </p>
                  <p className="text-xs text-muted-foreground capitalize">
                    {document.status}
                  </p>
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Right: Metadata sidebar */}
        <div className="space-y-4">
          {/* Actions */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm">Actions</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              <Button
                className="w-full justify-start"
                variant="outline"
                disabled={document.status !== "completed"}
                onClick={() =>
                  router.push(
                    `/chat?source=${document.id}`
                  )
                }
              >
                <MessageSquare className="mr-2 h-4 w-4" />
                Chat with this document
              </Button>
              <Button
                className="w-full justify-start"
                variant="outline"
                disabled={document.status !== "completed"}
                onClick={() => setShowAddToCollection(true)}
              >
                <FolderPlus className="mr-2 h-4 w-4" />
                Add to collection
              </Button>
              <Button
                className="w-full justify-start text-destructive"
                variant="outline"
                onClick={() => setShowDeleteDialog(true)}
              >
                <Trash2 className="mr-2 h-4 w-4" />
                Delete document
              </Button>
            </CardContent>
          </Card>

          {/* Metadata */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm">Details</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Type</span>
                <span>{getContentTypeLabel(document.content_type)}</span>
              </div>
              <Separator />
              <div className="flex justify-between">
                <span className="text-muted-foreground">Status</span>
                <span className="capitalize">{document.status}</span>
              </div>
              <Separator />
              {document.file_size_bytes != null && (
                <>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">File size</span>
                    <span>{formatFileSize(document.file_size_bytes)}</span>
                  </div>
                  <Separator />
                </>
              )}
              {document.page_count != null && (
                <>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Pages</span>
                    <span>{document.page_count}</span>
                  </div>
                  <Separator />
                </>
              )}
              {document.chunk_count != null && document.chunk_count > 0 && (
                <>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Chunks</span>
                    <span>{document.chunk_count}</span>
                  </div>
                  <Separator />
                </>
              )}
              <div className="flex justify-between">
                <span className="text-muted-foreground">Uploaded</span>
                <span>
                  {formatDistanceToNow(new Date(document.created_at), { addSuffix: true })}
                </span>
              </div>
            </CardContent>
          </Card>

          {/* Summary */}
          {document.summary && (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm">Summary</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground leading-relaxed">
                  {document.summary}
                </p>
                {document.key_topics && document.key_topics.length > 0 && (
                  <div className="mt-3 flex flex-wrap gap-1">
                    {document.key_topics.map((topic) => (
                      <Badge
                        key={topic}
                        variant="secondary"
                        className="text-[10px]"
                      >
                        {topic}
                      </Badge>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>

    {/* Add to collection modal */}
    {showAddToCollection && (
      <AddToCollectionModal
        videoIds={[id]}
        videoTitle={document.title}
        onClose={() => setShowAddToCollection(false)}
      />
    )}

    {/* Delete confirmation dialog */}
    <Dialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Delete document</DialogTitle>
          <DialogDescription>
            This will permanently delete &ldquo;{document.title}&rdquo; and its indexed data.
            This action cannot be undone.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" onClick={() => setShowDeleteDialog(false)}>
            Cancel
          </Button>
          <Button
            variant="destructive"
            disabled={deleteMutation.isPending}
            onClick={() => deleteMutation.mutate()}
          >
            {deleteMutation.isPending && (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            )}
            Delete
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
    </MainLayout>
  );
}

export default function DocumentDetailPage() {
  return (
    <Suspense
      fallback={
        <MainLayout>
          <div className="flex items-center justify-center py-20">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            <span className="ml-2 text-sm text-muted-foreground">
              Loading document...
            </span>
          </div>
        </MainLayout>
      }
    >
      <DocumentDetailPageInner />
    </Suspense>
  );
}
