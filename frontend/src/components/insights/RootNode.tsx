"use client";

import { memo } from "react";
import { Handle, Position, type NodeProps } from "reactflow";
import { cn } from "@/lib/utils";

export type RootNodeData = {
  label: string;
  topics_count?: number;
  isHighlighted?: boolean;
  isDimmed?: boolean;
  hasChildren?: boolean;
  isCollapsed?: boolean;
  onToggleCollapse?: (nodeId: string) => void;
};

export const RootNode = memo(({ data, selected }: NodeProps<RootNodeData>) => {
  const highlighted = Boolean(data.isHighlighted) || selected;
  const dimmed = Boolean(data.isDimmed) && !highlighted;
  const topicsCount = data.topics_count ?? 0;

  return (
    <div
      className={cn(
        "min-w-[260px] max-w-[360px] rounded-2xl px-6 py-4 shadow-sm ring-1 transition",
        "bg-indigo-200/60 ring-indigo-200/70 dark:bg-indigo-950/25 dark:ring-indigo-800/40",
        highlighted && "ring-2 ring-indigo-400/60",
        dimmed && "opacity-35"
      )}
    >
      <Handle type="source" position={Position.Right} />

      <p className="text-sm font-semibold leading-snug text-foreground">{data.label}</p>
      <p className="mt-1 text-xs text-muted-foreground">{topicsCount} topics</p>
    </div>
  );
});

RootNode.displayName = "RootNode";
