"use client";

import { useState } from "react";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { ChevronDown, Layers, Video, FileText } from "lucide-react";

interface Source {
  video_id: string;
  title?: string;
  is_selected: boolean;
  status?: string;
  selectable?: boolean;
  selectable_reason?: string;
  content_type?: string;
}

interface SourceSelectionPopoverProps {
  sources: Source[];
  selectedCount: number;
  totalCount: number;
  onToggleSource: (videoId: string) => void;
  onSelectAll: () => void;
  onDeselectAll: () => void;
  disabled?: boolean;
  error?: string | null;
}

export function SourceSelectionPopover({
  sources,
  selectedCount,
  totalCount,
  onToggleSource,
  onSelectAll,
  onDeselectAll,
  disabled,
  error,
}: SourceSelectionPopoverProps) {
  const [filter, setFilter] = useState("");
  const [open, setOpen] = useState(false);

  const filteredSources = sources.filter(
    (s) =>
      filter === "" ||
      (s.title || "Untitled").toLowerCase().includes(filter.toLowerCase())
  );

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button variant="outline" size="sm" className="gap-2 h-8">
          <Layers className="h-4 w-4" />
          <span className="hidden sm:inline">Sources</span>
          <Badge variant="secondary" className="ml-1 px-1.5 py-0 text-xs font-normal">
            {selectedCount}/{totalCount}
          </Badge>
          <ChevronDown className="h-3 w-3 text-muted-foreground" />
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-80 p-0">
        {/* Header with All/None */}
        <div className="flex items-center justify-between border-b px-3 py-2">
          <span className="text-sm font-medium">Select Sources</span>
          <div className="flex gap-1">
            <Button
              variant="ghost"
              size="sm"
              className="h-7 px-2 text-xs"
              onClick={onSelectAll}
              disabled={disabled || sources.length === 0}
            >
              All
            </Button>
            <Button
              variant="ghost"
              size="sm"
              className="h-7 px-2 text-xs"
              onClick={onDeselectAll}
              disabled={disabled || sources.length === 0}
            >
              None
            </Button>
          </div>
        </div>

        {/* Filter input - only show when 7+ sources */}
        {sources.length > 6 && (
          <div className="border-b px-3 py-2">
            <Input
              placeholder="Filter sources..."
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              className="h-8"
            />
          </div>
        )}

        {/* Source list */}
        <div className="max-h-64 overflow-y-auto p-2">
          {sources.length === 0 ? (
            <p className="px-2 py-3 text-center text-sm text-muted-foreground">
              No sources attached yet.
            </p>
          ) : filteredSources.length === 0 ? (
            <p className="px-2 py-3 text-center text-sm text-muted-foreground">
              No sources match filter.
            </p>
          ) : (
            <TooltipProvider delayDuration={300}>
              {filteredSources.map((source) => (
                <label
                  key={source.video_id}
                  className="flex items-center gap-3 rounded-md px-2 py-2 text-sm hover:bg-muted cursor-pointer transition-colors"
                >
                  <Checkbox
                    checked={source.is_selected}
                    onCheckedChange={() => onToggleSource(source.video_id)}
                    disabled={disabled || source.selectable === false}
                  />
                  {source.content_type && source.content_type !== "youtube" ? (
                    <FileText className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                  ) : (
                    <Video className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                  )}
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <span className="truncate flex-1">
                        {source.title || "Untitled"}
                      </span>
                    </TooltipTrigger>
                    <TooltipContent side="left" className="max-w-xs">
                      <p className="text-xs">{source.title || "Untitled"}</p>
                      {source.selectable === false && source.selectable_reason && (
                        <p className="mt-1 text-xs text-destructive">
                          {source.selectable_reason}
                        </p>
                      )}
                    </TooltipContent>
                  </Tooltip>
                  {source.status !== "completed" && (
                    <Badge variant="outline" className="text-xs shrink-0">
                      {source.status}
                    </Badge>
                  )}
                </label>
              ))}
            </TooltipProvider>
          )}
        </div>

        {/* Error display */}
        {error && (
          <div className="border-t px-3 py-2">
            <p className="text-xs text-destructive">{error}</p>
          </div>
        )}
      </PopoverContent>
    </Popover>
  );
}
