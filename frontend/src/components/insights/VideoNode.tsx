"use client";

import { memo } from "react";
import { Handle, Position, type NodeProps } from "reactflow";
import { Video } from "lucide-react";
import { cn } from "@/lib/utils";

export type VideoNodeData = {
  label: string;
  thumbnail_url?: string | null;
  duration_seconds?: number | null;
  isHighlighted?: boolean;
  isDimmed?: boolean;
};

export const VideoNode = memo(({ data, selected }: NodeProps<VideoNodeData>) => {
  const highlighted = Boolean(data.isHighlighted) || selected;
  const dimmed = Boolean(data.isDimmed) && !highlighted;

  return (
    <div
      className={cn(
        "min-w-[200px] max-w-[280px] rounded-lg border bg-muted/30 px-3 py-2 shadow-sm transition",
        highlighted ? "border-primary ring-2 ring-primary/20" : "border-border",
        dimmed && "opacity-40"
      )}
    >
      <Handle type="target" position={Position.Left} />

      <div className="flex items-start gap-2">
        <div className="mt-0.5 flex h-7 w-7 items-center justify-center rounded-md bg-background">
          <Video className="h-4 w-4 text-muted-foreground" />
        </div>
        <div className="min-w-0">
          <p className="line-clamp-2 text-xs font-medium leading-snug">
            {data.label}
          </p>
        </div>
      </div>
    </div>
  );
});

VideoNode.displayName = "VideoNode";

