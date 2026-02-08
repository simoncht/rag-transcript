"use client";

import { useQuery } from "@tanstack/react-query";
import { getCollectionThemes } from "@/lib/api/collections";
import { Badge } from "@/components/ui/badge";
import { useAuth, createParallelQueryFn } from "@/lib/auth";

interface CollectionThemesProps {
  collectionId: string;
  enabled?: boolean;
}

export function CollectionThemes({
  collectionId,
  enabled = true,
}: CollectionThemesProps) {
  const authProvider = useAuth();

  const { data, isLoading } = useQuery({
    queryKey: ["collection-themes", collectionId],
    queryFn: createParallelQueryFn(authProvider, () =>
      getCollectionThemes(collectionId)
    ),
    staleTime: 5 * 60 * 1000, // 5 minutes (server caches for 1 hour)
    enabled,
  });

  if (isLoading || !data || data.themes.length === 0) {
    return null;
  }

  return (
    <div className="flex flex-wrap gap-1.5">
      {data.themes.slice(0, 10).map((theme) => (
        <Badge
          key={theme.topic}
          variant="outline"
          className="text-xs font-normal"
          title={`${theme.count} video${theme.count !== 1 ? "s" : ""}`}
        >
          {theme.topic}
          {theme.count > 1 && (
            <span className="ml-1 text-muted-foreground">({theme.count})</span>
          )}
        </Badge>
      ))}
      {data.themes.length > 10 && (
        <Badge variant="secondary" className="text-xs font-normal">
          +{data.themes.length - 10} more
        </Badge>
      )}
    </div>
  );
}
