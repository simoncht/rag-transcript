"use client";

import { useQuery } from "@tanstack/react-query";
import Image from "next/image";
import { videosApi } from "@/lib/api/videos";
import { Badge } from "@/components/ui/badge";
import { useAuth, createParallelQueryFn } from "@/lib/auth";

interface SimilarVideosProps {
  videoId: string;
  enabled?: boolean;
}

export function SimilarVideos({ videoId, enabled = true }: SimilarVideosProps) {
  const authProvider = useAuth();

  const { data, isLoading } = useQuery({
    queryKey: ["similar-videos", videoId],
    queryFn: createParallelQueryFn(authProvider, () =>
      videosApi.getSimilar(videoId)
    ),
    staleTime: 5 * 60 * 1000,
    enabled,
  });

  if (isLoading || !data || data.similar_videos.length === 0) {
    return null;
  }

  const formatDuration = (seconds?: number) => {
    if (!seconds) return "";
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    if (hours > 0) return `${hours}h ${minutes}m`;
    return `${minutes}m`;
  };

  return (
    <div className="space-y-3">
      <h4 className="text-sm font-medium text-muted-foreground">Related content</h4>
      <div className="space-y-2">
        {data.similar_videos.map((item) => (
          <div
            key={item.video_id}
            className="flex items-start gap-3 rounded-md border p-2.5"
          >
            {item.thumbnail_url && (
              <Image
                src={item.thumbnail_url}
                alt={item.title}
                width={64}
                height={36}
                className="h-9 w-16 rounded object-cover"
                unoptimized
              />
            )}
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium">{item.title}</p>
              <div className="mt-1 flex flex-wrap gap-1">
                {item.shared_topics.slice(0, 3).map((topic) => (
                  <Badge
                    key={topic}
                    variant="secondary"
                    className="text-[10px]"
                  >
                    {topic}
                  </Badge>
                ))}
                {item.duration_seconds && (
                  <span className="text-[10px] text-muted-foreground">
                    {formatDuration(item.duration_seconds)}
                  </span>
                )}
              </div>
            </div>
            <span className="shrink-0 text-xs text-muted-foreground">
              {Math.round(item.similarity * 100)}%
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
