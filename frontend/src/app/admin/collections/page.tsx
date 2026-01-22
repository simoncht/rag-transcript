"use client";

import { useQuery } from "@tanstack/react-query";
import { adminApi } from "@/lib/api/admin";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { AlertCircle, Folder } from "lucide-react";

export default function AdminCollectionsPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["admin-content-overview"],
    queryFn: () => adminApi.getContentOverview(),
    refetchInterval: 30000,
  });

  const collections = data?.collections;

  return (
    <div className="container mx-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Collections</h1>
          <p className="text-muted-foreground">
            Inventory snapshot for playlists and shared collections.
          </p>
        </div>
        <Badge variant="outline">Read only</Badge>
      </div>

      {error && (
        <Card className="p-6 border-destructive">
          <div className="flex items-center gap-2 text-destructive">
            <AlertCircle className="h-5 w-5" />
            <p className="font-semibold">Failed to load collections</p>
          </div>
          <p className="mt-2 text-sm text-muted-foreground">
            {error instanceof Error ? error.message : "Unknown error"}
          </p>
        </Card>
      )}

      {isLoading ? (
        <div className="grid gap-4 md:grid-cols-3">
          {[...Array(3)].map((_, i) => (
            <Card key={i} className="p-6">
              <Skeleton className="h-4 w-24 mb-2" />
              <Skeleton className="h-8 w-16" />
            </Card>
          ))}
        </div>
      ) : collections ? (
        <div className="grid gap-4 md:grid-cols-3">
          <CollectionCard
            label="Total collections"
            value={collections.total}
            tone="neutral"
          />
          <CollectionCard
            label="With videos"
            value={collections.with_videos}
            tone="success"
          />
          <CollectionCard
            label="Empty"
            value={collections.empty}
            tone="muted"
          />
        </div>
      ) : null}

      <Card className="p-6">
        <div className="flex items-center gap-2 mb-4">
          <Folder className="h-4 w-4 text-muted-foreground" />
          <h2 className="text-lg font-semibold">Recent collection ids</h2>
        </div>
        {isLoading ? (
          <div className="space-y-2">
            {[...Array(6)].map((_, i) => (
              <Skeleton key={i} className="h-4 w-64" />
            ))}
          </div>
        ) : collections && collections.recent_created.length > 0 ? (
          <div className="flex flex-wrap gap-2">
            {collections.recent_created.map((id) => (
              <Badge key={id} variant="secondary">
                {id.slice(0, 8)}
              </Badge>
            ))}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">
            No recent collections.
          </p>
        )}
      </Card>
    </div>
  );
}

function CollectionCard({
  label,
  value,
  tone = "neutral",
}: {
  label: string;
  value: number;
  tone?: "neutral" | "success" | "muted";
}) {
  const tones = {
    neutral: "border",
    success: "border-green-200 bg-green-50 text-green-700",
    muted: "border-border text-muted-foreground",
  } as const;

  return (
    <Card className={`p-6 ${tones[tone]}`}>
      <p className="text-sm text-muted-foreground">{label}</p>
      <p className="text-3xl font-bold">{value}</p>
    </Card>
  );
}
