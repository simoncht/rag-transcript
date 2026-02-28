"use client";

import { useState, useCallback, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { Upload, X, FileText, Loader2, CheckCircle2, AlertCircle, Info } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { contentApi } from "@/lib/api/content";
import {
  getContentTypeLabel,
  getContentTypeBadgeClass,
  formatFileSize,
  ACCEPTED_MIME_TYPES,
} from "@/lib/content-type-utils";
import { cn } from "@/lib/utils";

interface FileEntry {
  file: File;
  id: string;
  status: "pending" | "uploading" | "success" | "error";
  progress: number;
  error?: string;
  contentType?: string;
  documentId?: string;
  pageCount?: number;
}

export interface UploadResult {
  successCount: number;
  failedCount: number;
  uploadedIds: string[];
}

function getContentTypeFromFile(file: File): string {
  const ext = file.name.split(".").pop()?.toLowerCase() || "";
  const extMap: Record<string, string> = {
    pdf: "pdf",
    docx: "docx",
    pptx: "pptx",
    xlsx: "xlsx",
    txt: "txt",
    md: "md",
    html: "html",
    htm: "html",
    epub: "epub",
    csv: "csv",
    rtf: "rtf",
    eml: "email",
  };
  return extMap[ext] || "unknown";
}

interface DocumentUploadZoneProps {
  onUploadComplete?: (result: UploadResult) => void;
  onViewDocument?: (id: string) => void;
  onViewDocuments?: () => void;
  maxSizeMB?: number;
}

export function DocumentUploadZone({
  onUploadComplete,
  onViewDocument,
  onViewDocuments,
  maxSizeMB: maxSizeMBProp = 100,
}: DocumentUploadZoneProps) {
  const { toast } = useToast();
  const queryClient = useQueryClient();

  // Fetch tier limits
  const { data: limits } = useQuery({
    queryKey: ["content-limits"],
    queryFn: () => contentApi.getLimits(),
  });

  const maxSizeMB = limits?.max_upload_size_mb ?? maxSizeMBProp;
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [files, setFiles] = useState<FileEntry[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);

  const addFiles = useCallback(
    async (newFiles: FileList | File[]) => {
      const entries: FileEntry[] = Array.from(newFiles).map((file) => ({
        file,
        id: `${file.name}-${Date.now()}-${Math.random().toString(36).slice(2)}`,
        status: "pending" as const,
        progress: 0,
        contentType: getContentTypeFromFile(file),
      }));

      // Validate file size
      const oversized = entries.filter(
        (e) => e.file.size > maxSizeMB * 1024 * 1024
      );
      if (oversized.length > 0) {
        toast({
          title: "File too large",
          description: `Maximum file size is ${maxSizeMB} MB. ${oversized.map((e) => e.file.name).join(", ")} exceeded the limit.`,
          variant: "destructive",
        });
        return;
      }

      // Validate file type
      const unknown = entries.filter((e) => e.contentType === "unknown");
      if (unknown.length > 0) {
        toast({
          title: "Unsupported file type",
          description: `${unknown.map((e) => e.file.name).join(", ")} - supported: PDF, DOCX, PPTX, XLSX, TXT, MD, HTML, EPUB, CSV, RTF, EML`,
          variant: "destructive",
        });
        return;
      }


      setFiles((prev) => [...prev, ...entries]);
    },
    [maxSizeMB, toast, limits]
  );

  const removeFile = useCallback((id: string) => {
    setFiles((prev) => prev.filter((f) => f.id !== id));
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback(
    async (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      if (e.dataTransfer.files.length > 0) {
        await addFiles(e.dataTransfer.files);
      }
    },
    [addFiles]
  );

  const handleFileSelect = useCallback(
    async (e: React.ChangeEvent<HTMLInputElement>) => {
      if (e.target.files && e.target.files.length > 0) {
        await addFiles(e.target.files);
      }
      // Reset input so same file can be selected again
      e.target.value = "";
    },
    [addFiles]
  );

  const uploadAll = useCallback(async () => {
    const pending = files.filter((f) => f.status === "pending");
    if (pending.length === 0) return;

    setIsUploading(true);
    let successCount = 0;
    let failedCount = 0;
    const uploadedIds: string[] = [];

    for (const entry of pending) {
      setFiles((prev) =>
        prev.map((f) =>
          f.id === entry.id ? { ...f, status: "uploading", progress: 30 } : f
        )
      );

      try {
        const result = await contentApi.upload(entry.file);
        successCount++;
        uploadedIds.push(result.content_id);
        setFiles((prev) =>
          prev.map((f) =>
            f.id === entry.id
              ? { ...f, status: "success", progress: 100, documentId: result.content_id }
              : f
          )
        );
        if (result.warning) {
          toast({
            title: "Processing notice",
            description: result.warning,
          });
        }
      } catch (err: any) {
        failedCount++;
        const message =
          err?.response?.data?.detail || err.message || "Upload failed";
        setFiles((prev) =>
          prev.map((f) =>
            f.id === entry.id
              ? { ...f, status: "error", progress: 0, error: message }
              : f
          )
        );
      }
    }

    setIsUploading(false);
    queryClient.invalidateQueries({ queryKey: ["documents"] });
    onUploadComplete?.({ successCount, failedCount, uploadedIds });
  }, [files, queryClient, onUploadComplete, toast]);

  const pendingCount = files.filter((f) => f.status === "pending").length;
  const completedCount = files.filter((f) => f.status === "success").length;
  const errorCount = files.filter((f) => f.status === "error").length;
  const totalSize = files
    .filter((f) => f.status === "pending")
    .reduce((sum, f) => sum + f.file.size, 0);
  const uploadedIds = files
    .filter((f) => f.status === "success" && f.documentId)
    .map((f) => f.documentId!);

  const clearCompleted = useCallback(() => {
    setFiles((prev) => prev.filter((f) => f.status !== "success"));
  }, []);

  return (
    <div className="space-y-4">
      {/* Drop zone */}
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        className={cn(
          "cursor-pointer rounded-lg border-2 border-dashed p-8 text-center transition-colors",
          isDragging
            ? "border-primary bg-primary/5"
            : "border-muted-foreground/25 hover:border-muted-foreground/50"
        )}
      >
        <Upload className="mx-auto h-10 w-10 text-muted-foreground/50" />
        <p className="mt-2 text-sm font-medium">
          Drop files here or click to browse
        </p>
        <p className="mt-1 text-xs text-muted-foreground">
          PDF, Word, PowerPoint, Excel, TXT, Markdown, HTML, EPUB, CSV, RTF,
          Email
        </p>
        <p className="text-xs text-muted-foreground">
          Max {maxSizeMB} MB per file
        </p>
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept={ACCEPTED_MIME_TYPES}
          onChange={handleFileSelect}
          className="hidden"
        />
      </div>

      {/* Tier limits info */}
      {limits && (
        <div className="flex items-start gap-2 rounded-md border border-muted bg-muted/30 px-3 py-2">
          <Info className="mt-0.5 h-3.5 w-3.5 shrink-0 text-muted-foreground" />
          <div className="text-xs text-muted-foreground">
            <p className="font-medium capitalize">{limits.tier} plan limits:</p>
            <ul className="mt-0.5 list-inside list-disc space-y-0">
              <li>Max file size: {limits.max_upload_size_mb} MB</li>
              <li>
                Max words per document:{" "}
                {limits.max_document_words === -1
                  ? "Unlimited"
                  : limits.max_document_words.toLocaleString()}
              </li>
            </ul>
          </div>
        </div>
      )}

      {/* File queue */}
      {files.length > 0 && (
        <div className="space-y-2">
          {files.map((entry) => (
            <div
              key={entry.id}
              className="flex items-center gap-3 rounded-md border px-3 py-2"
            >
              <FileText className="h-4 w-4 shrink-0 text-muted-foreground" />
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="truncate text-sm font-medium">
                    {entry.file.name}
                  </span>
                  {entry.contentType && (
                    <Badge
                      variant="outline"
                      className={cn(
                        "shrink-0 text-[10px]",
                        getContentTypeBadgeClass(entry.contentType)
                      )}
                    >
                      {getContentTypeLabel(entry.contentType)}
                    </Badge>
                  )}
                </div>
                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                  <span>
                    {formatFileSize(entry.file.size)}
                    {entry.pageCount != null && ` · ${entry.pageCount} pages`}
                  </span>
                  {entry.status === "error" && (
                    <span className="truncate max-w-[200px] text-destructive" title={entry.error}>{entry.error}</span>
                  )}
                </div>
                {entry.status === "uploading" && (
                  <Progress value={entry.progress} className="mt-1 h-1" />
                )}
              </div>
              <div className="shrink-0">
                {entry.status === "pending" && (
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-6 w-6"
                    onClick={(e) => {
                      e.stopPropagation();
                      removeFile(entry.id);
                    }}
                  >
                    <X className="h-3 w-3" />
                  </Button>
                )}
                {entry.status === "uploading" && (
                  <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                )}
                {entry.status === "success" && (
                  <CheckCircle2 className="h-4 w-4 text-emerald-500" />
                )}
                {entry.status === "error" && (
                  <AlertCircle className="h-4 w-4 text-destructive" />
                )}
              </div>
            </div>
          ))}

          {/* Upload button */}
          {pendingCount > 0 && (
            <div className="flex items-center justify-between rounded-md bg-muted/50 px-3 py-2">
              <span className="text-sm text-muted-foreground">
                {pendingCount} file{pendingCount !== 1 ? "s" : ""} (
                {formatFileSize(totalSize)})
              </span>
              <Button
                size="sm"
                onClick={uploadAll}
                disabled={isUploading}
              >
                {isUploading ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Upload className="mr-2 h-4 w-4" />
                )}
                Upload
              </Button>
            </div>
          )}

          {/* Success state with action buttons */}
          {completedCount > 0 && pendingCount === 0 && !isUploading && errorCount === 0 && (
            <div className="rounded-md bg-emerald-50 dark:bg-emerald-950/20 border border-emerald-200 dark:border-emerald-900/30 px-4 py-3">
              <div className="flex items-center gap-2 text-sm font-medium text-emerald-700 dark:text-emerald-400">
                <CheckCircle2 className="h-4 w-4" />
                {completedCount === 1
                  ? "1 document uploaded"
                  : `${completedCount} documents uploaded`}
              </div>
              <p className="mt-1 text-xs text-emerald-600/80 dark:text-emerald-500/70">
                Processing has started. You can chat with {completedCount === 1 ? "it" : "them"} once ready.
              </p>
              <div className="mt-3 flex items-center gap-2">
                {completedCount === 1 && uploadedIds[0] && onViewDocument ? (
                  <Button
                    size="sm"
                    onClick={() => onViewDocument(uploadedIds[0])}
                  >
                    View document
                  </Button>
                ) : onViewDocuments ? (
                  <Button
                    size="sm"
                    onClick={onViewDocuments}
                  >
                    View documents
                  </Button>
                ) : null}
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={clearCompleted}
                >
                  Upload more
                </Button>
              </div>
            </div>
          )}

          {/* Mixed results: show clear button when there are errors alongside successes */}
          {completedCount > 0 && errorCount > 0 && pendingCount === 0 && !isUploading && (
            <div className="flex items-center justify-between rounded-md bg-muted/50 px-3 py-2">
              <span className="text-sm text-muted-foreground">
                {completedCount} succeeded, {errorCount} failed
              </span>
              <Button
                size="sm"
                variant="ghost"
                onClick={clearCompleted}
              >
                Clear completed
              </Button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
