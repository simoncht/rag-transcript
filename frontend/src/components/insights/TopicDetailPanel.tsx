"use client";

import { useEffect } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, Play, X } from "lucide-react";

import { insightsApi } from "@/lib/api/insights";
import { videosApi } from "@/lib/api/videos";
import type { TopicInsightChunk } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";

type Props = {
  conversationId: string;
  topicId: string;
  onClose: () => void;
};

export function TopicDetailPanel({ conversationId, topicId, onClose }: Props) {
  const queryClient = useQueryClient();

  const { data, isLoading, isError } = useQuery({
    queryKey: ["topic-chunks", conversationId, topicId],
    queryFn: () => insightsApi.getTopicChunks(conversationId, topicId),
    enabled: Boolean(conversationId && topicId),
  });

  useEffect(() => {
    const videoIds = new Set((data?.chunks ?? []).map((chunk) => chunk.video_id).filter(Boolean));
    videoIds.forEach((videoId) => {
      queryClient.prefetchQuery({
        queryKey: ["video", videoId],
        queryFn: () => videosApi.get(videoId),
        staleTime: 5 * 60 * 1000,
      });
    });
  }, [data?.chunks, queryClient]);

  const handleJumpToTimestamp = async (chunk: TopicInsightChunk) => {
    const seconds = Math.max(0, Math.floor(chunk.start_timestamp ?? 0));
    const popup = window.open("about:blank", "_blank");

    try {
      const video = await queryClient.fetchQuery({
        queryKey: ["video", chunk.video_id],
        queryFn: () => videosApi.get(chunk.video_id),
        staleTime: 5 * 60 * 1000,
      });

      const url = new URL(video.youtube_url);
      url.searchParams.set("t", `${seconds}s`);

      const target = url.toString();
      if (popup) {
        popup.location.href = target;
        popup.focus?.();
        return;
      }

      window.open(target, "_blank", "noopener,noreferrer");
    } catch (error) {
      popup?.close();
      console.error("[insights] jump-to-timestamp failed", error);
    }
  };

  return (
    <div className="flex h-full w-[340px] flex-col border-l bg-background">
      <div className="flex items-start justify-between gap-2 p-4">
        <div className="min-w-0">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Topic
          </p>
          <h3 className="mt-1 line-clamp-2 text-sm font-semibold">
            {data?.topic_label ?? topicId}
          </h3>
        </div>
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8"
          onClick={onClose}
        >
          <X className="h-4 w-4" />
        </Button>
      </div>

      {isLoading ? (
        <div className="flex flex-1 items-center justify-center text-sm text-muted-foreground">
          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          Loading chunks...
        </div>
      ) : isError ? (
        <div className="flex flex-1 items-center justify-center px-4 text-sm text-destructive">
          Failed to load topic chunks.
        </div>
      ) : (
        <ScrollArea className="flex-1 px-4 pb-4">
          <div className="space-y-3">
            {(data?.chunks ?? []).map((chunk) => (
              <div
                key={chunk.chunk_id}
                className="rounded-lg border border-border bg-muted/20 p-3"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="line-clamp-2 text-xs font-semibold">
                      {chunk.video_title}
                    </p>
                    <div className="mt-1 flex flex-wrap items-center gap-2">
                      <Badge variant="outline" className="text-[10px]">
                        {chunk.timestamp_display}
                      </Badge>
                      {chunk.chunk_title ? (
                        <span className="line-clamp-1 text-[11px] text-muted-foreground">
                          {chunk.chunk_title}
                        </span>
                      ) : null}
                    </div>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-8 gap-2"
                    onClick={() => handleJumpToTimestamp(chunk)}
                  >
                    <Play className="h-3.5 w-3.5" />
                    Jump
                  </Button>
                </div>

                <p className="mt-2 line-clamp-6 text-xs text-muted-foreground">
                  {chunk.text}
                </p>
              </div>
            ))}

            {(data?.chunks ?? []).length === 0 ? (
              <p className="text-xs text-muted-foreground">
                No chunks found for this topic.
              </p>
            ) : null}
          </div>
        </ScrollArea>
      )}
    </div>
  );
}
