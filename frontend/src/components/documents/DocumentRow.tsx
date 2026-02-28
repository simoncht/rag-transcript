"use client";

import { useRouter } from "next/navigation";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Checkbox } from "@/components/ui/checkbox";
import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { TableCell, TableRow } from "@/components/ui/table";
import { MessageSquare, Trash2, ExternalLink, RefreshCw, Loader2, FolderPlus, XCircle } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { contentApi } from "@/lib/api/content";
import {
  getContentTypeConfig,
  getContentTypeBadgeClass,
  getContentTypeLabel,
  formatFileSize,
} from "@/lib/content-type-utils";
import type { ContentItem } from "@/lib/types";
import { cn } from "@/lib/utils";

function formatEta(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.round((seconds % 3600) / 60);
  return minutes > 0 ? `${hours}h ${minutes}m` : `${hours}h`;
}

function getStatusBadgeClass(status: string, activityStatus?: string): string {
  switch (status) {
    case "completed":
      return "border-emerald-200 bg-emerald-50 text-emerald-700";
    case "failed":
      return "border-destructive/40 bg-destructive/10 text-destructive";
    case "canceled":
      return "border-orange-200 bg-orange-50 text-orange-700";
    case "extracting":
    case "extracted":
    case "chunking":
    case "enriching":
    case "indexing":
      if (activityStatus === "unresponsive") return "border-red-200 bg-red-50 text-red-700";
      if (activityStatus === "stalled") return "border-amber-200 bg-amber-50 text-amber-700";
      if (activityStatus === "slow") return "border-yellow-200 bg-yellow-50 text-yellow-700";
      return "border-sky-200 bg-sky-50 text-sky-700";
    default:
      return "border-gray-200 bg-gray-50 text-gray-700";
  }
}

function formatTimeSince(seconds: number): string {
  if (seconds < 60) return `${seconds}s ago`;
  if (seconds < 3600) return `${Math.round(seconds / 60)}m ago`;
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.round((seconds % 3600) / 60);
  return minutes > 0 ? `${hours}h ${minutes}m ago` : `${hours}h ago`;
}

function ActivityIndicator({ document }: { document: ContentItem }) {
  const status = document.activity_status;
  const rate = document.processing_rate;
  const secondsSince = document.seconds_since_update;
  const rateStr = rate != null && rate > 0 ? ` (${rate} chunks/min)` : "";

  if (!status || status === "active") {
    return (
      <span className="inline-flex items-center gap-1 text-[10px] text-emerald-600">
        <span className="inline-block h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
        Active{rateStr}
      </span>
    );
  }

  if (status === "slow") {
    return (
      <span className="inline-flex items-center gap-1 text-[10px] text-yellow-600">
        <span className="inline-block h-1.5 w-1.5 rounded-full bg-yellow-500" />
        Last update {secondsSince != null ? formatTimeSince(secondsSince) : "recently"}{rateStr}
      </span>
    );
  }

  if (status === "stalled") {
    return (
      <span className="inline-flex items-center gap-1 text-[10px] font-medium text-amber-600">
        <span className="inline-block h-1.5 w-1.5 rounded-full bg-amber-500" />
        No updates for {secondsSince != null ? formatTimeSince(secondsSince) : ">5m"}
      </span>
    );
  }

  // unresponsive
  return (
    <span className="inline-flex items-center gap-1 text-[10px] font-medium text-red-600">
      <span className="inline-block h-1.5 w-1.5 rounded-full bg-red-500" />
      Processing appears stopped{secondsSince != null ? ` (${formatTimeSince(secondsSince)})` : ""}
    </span>
  );
}

interface DocumentRowProps {
  document: ContentItem;
  isSelected: boolean;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
  onView: (id: string) => void;
  onCancel?: (id: string) => void;
  onAddToCollection?: (id: string) => void;
}

export function DocumentRow({
  document,
  isSelected,
  onSelect,
  onDelete,
  onView,
  onCancel,
  onAddToCollection,
}: DocumentRowProps) {
  const router = useRouter();
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const config = getContentTypeConfig(document.content_type);
  const TypeIcon = config.icon;
  const isProcessing = !["completed", "failed", "canceled"].includes(
    document.status
  );
  const isCompleted = document.status === "completed";
  const isFailed = document.status === "failed";
  const isCanceled = document.status === "canceled";
  const isReprocessable = isFailed || isCanceled;

  const reprocessMutation = useMutation({
    mutationFn: () => contentApi.reprocess(document.id),
    onSuccess: () => {
      toast({ title: "Reprocessing started" });
      queryClient.invalidateQueries({ queryKey: ["documents"] });
    },
    onError: (err: any) => {
      toast({
        title: "Reprocess failed",
        description: err?.response?.data?.detail || err.message,
        variant: "destructive",
      });
    },
  });

  return (
    <TableRow
      className={cn(
        isSelected && "bg-muted/50",
        isCompleted && "cursor-pointer",
        isProcessing && (!document.activity_status || document.activity_status === "active") && "border-l-2 border-sky-400",
        isProcessing && document.activity_status === "slow" && "border-l-2 border-yellow-400",
        isProcessing && document.activity_status === "stalled" && "border-l-2 border-amber-400",
        isProcessing && document.activity_status === "unresponsive" && "border-l-2 border-red-400",
        !isCompleted && !isFailed && !isProcessing && "opacity-70",
      )}
      onClick={() => {
        if (isCompleted) {
          onView(document.id);
        }
      }}
    >
      {/* Checkbox */}
      <TableCell className="w-12">
        <Checkbox
          checked={isSelected}
          onCheckedChange={() => onSelect(document.id)}
          onClick={(e) => e.stopPropagation()}
        />
      </TableCell>

      {/* Document info */}
      <TableCell className="w-[40%]">
        <div className="flex items-start gap-3">
          <div
            className={cn(
              "flex h-9 w-9 shrink-0 items-center justify-center rounded-md",
              config.bgColor
            )}
          >
            <TypeIcon className={cn("h-4 w-4", config.textColor)} />
          </div>
          <div className="min-w-0">
            <p className="truncate text-sm font-medium">{document.title}</p>
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              {document.original_filename && (
                <span className="truncate max-w-[200px]">
                  {document.original_filename}
                </span>
              )}
              {document.page_count != null && document.page_count > 0 && (
                <>
                  <span>&bull;</span>
                  <span>
                    {document.page_count} page
                    {document.page_count !== 1 ? "s" : ""}
                  </span>
                </>
              )}
              {document.chunk_count != null && document.chunk_count > 0 && (
                <>
                  <span>&bull;</span>
                  <span>{document.chunk_count} chunks</span>
                </>
              )}
            </div>
          </div>
        </div>
      </TableCell>

      {/* Type */}
      <TableCell className="w-[12%]">
        <Badge
          variant="outline"
          className={cn("text-[10px]", getContentTypeBadgeClass(document.content_type))}
        >
          {getContentTypeLabel(document.content_type)}
        </Badge>
      </TableCell>

      {/* Status */}
      <TableCell className="w-[15%]">
        <div>
          <span className="inline-flex items-center gap-1">
            <Badge
              variant="outline"
              className={cn(
                "text-[10px]",
                getStatusBadgeClass(document.status, document.activity_status),
                isProcessing && (!document.activity_status || document.activity_status === "active") && "animate-pulse",
              )}
            >
              {document.status}
            </Badge>
            {isProcessing && (!document.activity_status || document.activity_status === "active" || document.activity_status === "slow") && (
              <Loader2 className="inline h-3 w-3 animate-spin text-sky-500" />
            )}
          </span>
          {isProcessing && document.progress_percent != null && (
            <div className="mt-1.5">
              <Progress
                value={document.progress_percent}
                className="h-1.5"
              />
              <div className="mt-0.5 flex flex-col gap-0.5">
                {document.chunks_enriched != null && document.total_chunks != null ? (
                  <p className="text-[10px] text-muted-foreground">
                    {document.chunks_enriched}/{document.total_chunks} chunks
                  </p>
                ) : (
                  <p className="text-[10px] text-muted-foreground">
                    {Math.round(document.progress_percent)}%
                  </p>
                )}
                {document.eta_seconds != null && document.eta_seconds > 0 && document.chunks_enriched != null && document.chunks_enriched >= 5 && (
                  <p className="text-[10px] text-muted-foreground">
                    ~{formatEta(document.eta_seconds)} left
                  </p>
                )}
                {isProcessing && <ActivityIndicator document={document} />}
              </div>
            </div>
          )}
          {document.error_message && (
            <Tooltip>
              <TooltipTrigger asChild>
                <p className="mt-0.5 cursor-help truncate text-[10px] text-destructive max-w-[250px]">
                  {document.error_message}
                </p>
              </TooltipTrigger>
              <TooltipContent side="bottom" className="max-w-[400px]">
                <p className="text-xs">{document.error_message}</p>
              </TooltipContent>
            </Tooltip>
          )}
        </div>
      </TableCell>

      {/* Size */}
      <TableCell className="w-[10%]">
        <span className="text-sm text-muted-foreground">
          {document.file_size_bytes
            ? formatFileSize(document.file_size_bytes)
            : "-"}
        </span>
      </TableCell>

      {/* Actions */}
      <TableCell className="w-[23%] text-right">
        <div className="flex items-center justify-end gap-1">
          {isCompleted && (
            <>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8"
                    onClick={(e) => {
                      e.stopPropagation();
                      router.push(`/chat?source=${document.id}`);
                    }}
                  >
                    <MessageSquare className="h-4 w-4" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Chat with document</TooltipContent>
              </Tooltip>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8"
                    onClick={(e) => {
                      e.stopPropagation();
                      onView(document.id);
                    }}
                  >
                    <ExternalLink className="h-4 w-4" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>View document</TooltipContent>
              </Tooltip>
              {onAddToCollection && (
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button
                      variant="outline"
                      size="sm"
                      className="gap-1"
                      onClick={(e) => {
                        e.stopPropagation();
                        onAddToCollection(document.id);
                      }}
                    >
                      <FolderPlus className="h-3.5 w-3.5" />
                      Add to collection
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>Add to collection</TooltipContent>
                </Tooltip>
              )}
            </>
          )}
          {isProcessing && onCancel && (
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8 text-amber-600 hover:text-amber-700"
                  onClick={(e) => {
                    e.stopPropagation();
                    onCancel(document.id);
                  }}
                >
                  <XCircle className="h-4 w-4" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>Cancel processing</TooltipContent>
            </Tooltip>
          )}
          {isReprocessable && (
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  className={cn(
                    "h-8 w-8",
                    reprocessMutation.isPending
                      ? "text-orange-600"
                      : "text-muted-foreground hover:text-blue-600"
                  )}
                  disabled={reprocessMutation.isPending}
                  onClick={(e) => {
                    e.stopPropagation();
                    reprocessMutation.mutate();
                  }}
                >
                  {reprocessMutation.isPending ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <RefreshCw className="h-4 w-4" />
                  )}
                </Button>
              </TooltipTrigger>
              <TooltipContent>Reprocess</TooltipContent>
            </Tooltip>
          )}
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8 text-destructive hover:text-destructive"
                onClick={(e) => {
                  e.stopPropagation();
                  onDelete(document.id);
                }}
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>Delete</TooltipContent>
          </Tooltip>
        </div>
      </TableCell>
    </TableRow>
  );
}
