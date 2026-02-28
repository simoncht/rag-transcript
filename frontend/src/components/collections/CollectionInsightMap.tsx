"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api/client";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Loader2, Network, RefreshCw } from "lucide-react";
import type { CollectionInsightsResponse } from "@/lib/types";

interface CollectionInsightMapProps {
  collectionId: string;
  videoCount: number;
}

export function CollectionInsightMap({ collectionId, videoCount }: CollectionInsightMapProps) {
  const [showMap, setShowMap] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);

  const { data, isLoading, isFetching, error } = useQuery<CollectionInsightsResponse>({
    queryKey: ["collection-insights", collectionId, refreshKey],
    queryFn: async () => {
      const params = refreshKey > 0 ? "?refresh=true" : "";
      const res = await apiClient.get(`/collections/${collectionId}/insights${params}`);
      return res.data;
    },
    enabled: showMap && videoCount >= 2,
    staleTime: 5 * 60_000,
  });

  // Need at least 2 completed videos for meaningful insights
  if (videoCount < 2) return null;

  if (!showMap) {
    return (
      <Button
        variant="outline"
        size="sm"
        className="gap-1.5 text-xs"
        onClick={() => setShowMap(true)}
      >
        <Network className="h-3.5 w-3.5" />
        Topic Map
      </Button>
    );
  }

  const graph = data?.graph;
  const metadata = data?.metadata;
  const topicNodes = graph?.nodes?.filter(n => n.type === "topic") ?? [];

  return (
    <div className="mt-3 rounded-lg border bg-background/60 p-4 space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Network className="h-4 w-4 text-muted-foreground" />
          <span className="text-sm font-medium">Topic Map</span>
          {metadata && (
            <Badge variant="secondary" className="text-[10px]">
              {metadata.topics_count} topics
            </Badge>
          )}
          {metadata?.cached && (
            <span className="text-[10px] text-muted-foreground">cached</span>
          )}
        </div>
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="sm"
            className="h-7 text-xs gap-1"
            onClick={() => setRefreshKey(k => k + 1)}
            disabled={isFetching}
          >
            <RefreshCw className={`h-3 w-3 ${isFetching ? "animate-spin" : ""}`} />
            Refresh
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="h-7 text-xs"
            onClick={() => setShowMap(false)}
          >
            Hide
          </Button>
        </div>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-8 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin mr-2" />
          Generating topic map...
        </div>
      ) : error ? (
        <div className="text-center py-6 text-sm text-muted-foreground">
          {(error as any)?.response?.data?.detail || (error as Error).message || "Failed to generate topic map."}
        </div>
      ) : topicNodes.length === 0 ? (
        <div className="text-center py-6 text-sm text-muted-foreground">
          Not enough content to generate a topic map.
        </div>
      ) : (
        <div className="space-y-2">
          {topicNodes.map((node) => (
            <div
              key={node.id}
              className="rounded-md border bg-muted/20 px-3 py-2"
            >
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium">{node.data.label}</p>
                  {node.data.description && (
                    <p className="text-xs text-muted-foreground mt-0.5 line-clamp-2">
                      {node.data.description}
                    </p>
                  )}
                </div>
                {node.data.chunk_count != null && (
                  <Badge variant="outline" className="text-[10px] shrink-0">
                    {node.data.chunk_count} chunks
                  </Badge>
                )}
              </div>
            </div>
          ))}

          {metadata?.generation_time_seconds != null && (
            <p className="text-[10px] text-muted-foreground text-right">
              Generated in {metadata.generation_time_seconds.toFixed(1)}s
              {metadata.total_chunks_analyzed > 0 && (
                <> from {metadata.total_chunks_analyzed} chunks</>
              )}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
