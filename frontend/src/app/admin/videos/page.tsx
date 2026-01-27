"use client";

import { useQuery } from "@tanstack/react-query";
import { adminApi } from "@/lib/api/admin";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import { AlertCircle, Film } from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import { parseUTCDate } from "@/lib/utils";

export default function AdminVideosPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["admin-content-overview"],
    queryFn: () => adminApi.getContentOverview(),
    refetchInterval: 30000,
  });

  const videos = data?.videos;

  return (
    <div className="container mx-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Video Ingestion</h1>
          <p className="text-muted-foreground">
            Read-only operational view of ingestion and processing health.
          </p>
        </div>
        <Badge variant="outline">Admin only</Badge>
      </div>

      {error && (
        <Card className="p-6 border-destructive">
          <div className="flex items-center gap-2 text-destructive">
            <AlertCircle className="h-5 w-5" />
            <p className="font-semibold">Failed to load overview</p>
          </div>
          <p className="mt-2 text-sm text-muted-foreground">
            {error instanceof Error ? error.message : "Unknown error"}
          </p>
        </Card>
      )}

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {isLoading ? (
          [...Array(4)].map((_, i) => (
            <Card key={i} className="p-6">
              <Skeleton className="h-4 w-24 mb-2" />
              <Skeleton className="h-8 w-16" />
            </Card>
          ))
        ) : videos ? (
          <>
            <StatusCard label="Total" value={videos.total} />
            <StatusCard label="Completed" value={videos.completed} tone="success" />
            <StatusCard label="Processing" value={videos.processing} tone="warning" />
            <StatusCard label="Failed" value={videos.failed} tone="danger" />
          </>
        ) : null}
      </div>

      <Card>
        <div className="flex items-center justify-between p-4 border-b">
          <div className="flex items-center gap-2">
            <Film className="h-4 w-4 text-muted-foreground" />
            <h2 className="text-lg font-semibold">Recent videos</h2>
          </div>
          <Badge variant="secondary">
            {videos?.recent.length ?? 0} shown
          </Badge>
        </div>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Title</TableHead>
              <TableHead>User</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Progress</TableHead>
              <TableHead>Created</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              [...Array(6)].map((_, i) => (
                <TableRow key={i}>
                  <TableCell>
                    <Skeleton className="h-4 w-48" />
                  </TableCell>
                  <TableCell>
                    <Skeleton className="h-4 w-32" />
                  </TableCell>
                  <TableCell>
                    <Skeleton className="h-4 w-16" />
                  </TableCell>
                  <TableCell>
                    <Skeleton className="h-4 w-16" />
                  </TableCell>
                  <TableCell>
                    <Skeleton className="h-4 w-24" />
                  </TableCell>
                </TableRow>
              ))
            ) : videos && videos.recent.length > 0 ? (
              videos.recent.map((video) => (
                <TableRow key={video.id}>
                  <TableCell className="max-w-lg">
                    <p className="font-medium leading-tight">{video.title}</p>
                    <p className="text-xs text-muted-foreground">
                      {video.id.slice(0, 8)}
                    </p>
                  </TableCell>
                  <TableCell className="text-sm">
                    {video.user_email || "Unknown user"}
                  </TableCell>
                  <TableCell>
                    <Badge variant="secondary">{video.status}</Badge>
                    {video.error_message && (
                      <p className="text-xs text-destructive mt-1">
                        {video.error_message}
                      </p>
                    )}
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {Math.round(video.progress_percent)}%
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {formatDistanceToNow(parseUTCDate(video.created_at), {
                      addSuffix: true,
                    })}
                  </TableCell>
                </TableRow>
              ))
            ) : (
              <TableRow>
                <TableCell colSpan={5} className="text-center py-10">
                  <p className="text-muted-foreground">No recent videos.</p>
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </Card>
    </div>
  );
}

function StatusCard({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone?: "success" | "warning" | "danger";
}) {
  const tones = {
    success: "text-green-600 bg-green-50 border-green-200",
    warning: "text-amber-600 bg-amber-50 border-amber-200",
    danger: "text-red-600 bg-red-50 border-red-200",
  } as const;

  return (
    <Card
      className={`p-6 ${tone ? tones[tone] : ""} border transition-colors`}
    >
      <p className="text-sm text-muted-foreground">{label}</p>
      <p className="text-3xl font-bold">{value}</p>
    </Card>
  );
}
