"use client";

import { useState, useMemo } from "react";
import { Tag as TagIcon, Check, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

interface TagOption {
  name: string;
  count: number;
}

interface TagFilterProps {
  availableTags: TagOption[];
  selectedTags: string[];
  onTagsChange: (tags: string[]) => void;
}

export function TagFilter({ availableTags, selectedTags, onTagsChange }: TagFilterProps) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");

  const filteredTags = useMemo(() => {
    if (!search.trim()) return availableTags;
    const lower = search.toLowerCase();
    return availableTags.filter((t) => t.name.toLowerCase().includes(lower));
  }, [availableTags, search]);

  const toggleTag = (tag: string) => {
    if (selectedTags.includes(tag)) {
      onTagsChange(selectedTags.filter((t) => t !== tag));
    } else {
      onTagsChange([...selectedTags, tag]);
    }
  };

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button variant="outline" size="sm" className="h-8 gap-1 text-xs">
          <TagIcon className="h-3.5 w-3.5" />
          Tags
          {selectedTags.length > 0 && (
            <Badge variant="secondary" className="ml-1 h-4 min-w-4 px-1 text-[10px]">
              {selectedTags.length}
            </Badge>
          )}
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-56 p-0" align="start">
        <div className="p-2 border-b">
          <div className="relative">
            <Search className="pointer-events-none absolute left-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search tags..."
              className="h-8 pl-8 text-xs"
            />
          </div>
        </div>
        <div className="max-h-48 overflow-y-auto p-1">
          {filteredTags.length === 0 ? (
            <p className="p-2 text-center text-xs text-muted-foreground">No tags found</p>
          ) : (
            filteredTags.map((tag) => {
              const isSelected = selectedTags.includes(tag.name);
              return (
                <button
                  key={tag.name}
                  type="button"
                  onClick={() => toggleTag(tag.name)}
                  className={cn(
                    "flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-xs hover:bg-muted",
                    isSelected && "bg-muted"
                  )}
                >
                  <div className={cn(
                    "flex h-4 w-4 items-center justify-center rounded border",
                    isSelected ? "border-primary bg-primary text-primary-foreground" : "border-muted-foreground/30"
                  )}>
                    {isSelected && <Check className="h-3 w-3" />}
                  </div>
                  <span className="flex-1 text-left truncate">{tag.name}</span>
                  <span className="text-muted-foreground">{tag.count}</span>
                </button>
              );
            })
          )}
        </div>
        {selectedTags.length > 0 && (
          <div className="border-t p-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onTagsChange([])}
              className="h-7 w-full text-xs"
            >
              Clear tags
            </Button>
          </div>
        )}
      </PopoverContent>
    </Popover>
  );
}
