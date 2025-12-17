"use client";

import { memo } from "react";
import { Handle, Position, type NodeProps } from "reactflow";
import { cn } from "@/lib/utils";
import { ChevronRight, ChevronDown } from "lucide-react";

export type TopicNodeData = {
  label: string;
  description?: string;
  chunk_count?: number;
  parent_topic_id?: string;
  isHighlighted?: boolean;
  isDimmed?: boolean;
  depth?: number;
  hasChildren?: boolean;
  isCollapsed?: boolean;
  onToggleCollapse?: (nodeId: string) => void;
};

export const TopicNode = memo(({ id, data, selected, type }: NodeProps<TopicNodeData>) => {
  const highlighted = Boolean(data.isHighlighted) || selected;
  const dimmed = Boolean(data.isDimmed) && !highlighted;
  const depth = data.depth ?? 1;
  const isMoment = type === "moment";
  const hasChildren = Boolean(data.hasChildren) || (!isMoment && data.hasChildren == null);
  const isCollapsed = Boolean(data.isCollapsed);

  return (
    <div
      className={cn(
        "min-w-[240px] max-w-[360px] rounded-2xl px-5 py-3 shadow-sm ring-1 transition",
        depth <= 1
          ? "bg-sky-200/50 ring-sky-200/70 dark:bg-sky-950/25 dark:ring-sky-800/40"
          : "bg-emerald-200/50 ring-emerald-200/70 dark:bg-emerald-950/25 dark:ring-emerald-800/40",
        highlighted && "ring-2 ring-indigo-400/60",
        dimmed && "opacity-35"
      )}
    >
      <Handle type="target" position={Position.Left} />
      {hasChildren ? <Handle type="source" position={Position.Right} /> : null}

      <div className="flex items-start justify-between gap-3">
        <p className="text-sm font-medium leading-snug text-foreground">{data.label}</p>
        {data.onToggleCollapse && hasChildren ? (
          <button
            type="button"
            className={cn(
              "mt-0.5 inline-flex h-6 w-6 items-center justify-center rounded-full bg-white/70 text-foreground shadow-sm ring-1 ring-black/5 transition hover:bg-white dark:bg-white/10 dark:hover:bg-white/15",
              isCollapsed && "text-muted-foreground"
            )}
            onClick={(event) => {
              event.stopPropagation();
              data.onToggleCollapse?.(id);
            }}
            aria-label={isCollapsed ? "Expand branch" : "Collapse branch"}
          >
            {isCollapsed ? (
              <ChevronRight className="h-3.5 w-3.5" />
            ) : (
              <ChevronDown className="h-3.5 w-3.5" />
            )}
          </button>
        ) : null}
      </div>


    </div>
  );
});

TopicNode.displayName = "TopicNode";
