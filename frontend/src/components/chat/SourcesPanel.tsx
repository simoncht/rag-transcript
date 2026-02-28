"use client";

import { useState, useMemo, useEffect } from "react";
import { useSourcesPanel, type LibraryContentItem } from "./SourcesPanelContext";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  Sheet,
  SheetContent,
} from "@/components/ui/sheet";
import { cn } from "@/lib/utils";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  Video,
  FileText,
  Folder,
  Search,
  Plus,
  PanelRightClose,
  PanelRightOpen,
  Loader2,
  Upload,
  Link2,
  ChevronDown,
  Check,
} from "lucide-react";
import { AddContentPanel } from "@/components/videos/AddContentPanel";
import type { ConversationSource } from "@/lib/types";

function formatDuration(seconds?: number) {
  if (!seconds) return "";
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  if (h > 0) return `${h}:${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
  return `${m}:${s.toString().padStart(2, "0")}`;
}

function CollectionPicker({
  collections,
  selectedCollectionId,
  onCollectionChange,
  onSelectionChange,
}: {
  collections: { id: string; name: string; video_count: number }[];
  selectedCollectionId: string;
  onCollectionChange: (id: string) => void;
  onSelectionChange: (ids: string[]) => void;
}) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");

  const filtered = useMemo(() => {
    if (!search.trim()) return collections;
    const lower = search.toLowerCase();
    return collections.filter((c) => {
      const name = c.name.toLowerCase();
      // Exact substring match first, then fuzzy (all chars in order)
      if (name.includes(lower)) return true;
      let j = 0;
      for (let i = 0; i < name.length && j < lower.length; i++) {
        if (name[i] === lower[j]) j++;
      }
      return j === lower.length;
    });
  }, [collections, search]);

  const selectedName = collections.find((c) => c.id === selectedCollectionId)?.name;

  return (
    <div className="space-y-1.5">
      <p className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider">Collections</p>
      <Popover open={open} onOpenChange={(v) => { setOpen(v); if (!v) setSearch(""); }}>
        <PopoverTrigger asChild>
          <Button variant="outline" size="sm" className="w-full h-7 justify-between gap-1 text-xs px-2">
            <span className="flex items-center gap-1 truncate">
              <Folder className="h-3 w-3 flex-shrink-0" />
              {selectedName ? selectedName : `Collections (${collections.length})`}
            </span>
            <ChevronDown className="h-3 w-3 flex-shrink-0 opacity-50" />
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-56 p-0" align="start">
          <div className="p-2 border-b">
            <div className="relative">
              <Search className="pointer-events-none absolute left-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search collections..."
                className="h-8 pl-8 text-xs"
              />
            </div>
          </div>
          <div className="max-h-60 overflow-y-auto p-1">
            {filtered.length === 0 ? (
              <p className="p-2 text-center text-xs text-muted-foreground">No collections found</p>
            ) : (
              filtered.map((c) => {
                const isSelected = selectedCollectionId === c.id;
                return (
                  <button
                    key={c.id}
                    type="button"
                    onClick={() => {
                      onCollectionChange(isSelected ? "" : c.id);
                      if (!isSelected) onSelectionChange([]);
                      setOpen(false);
                    }}
                    className={cn(
                      "flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-xs hover:bg-muted",
                      isSelected && "bg-muted"
                    )}
                  >
                    <div className={cn(
                      "flex h-4 w-4 items-center justify-center rounded-full border",
                      isSelected ? "border-primary bg-primary text-primary-foreground" : "border-muted-foreground/30"
                    )}>
                      {isSelected && <Check className="h-3 w-3" />}
                    </div>
                    <span className="flex-1 text-left truncate">{c.name}</span>
                    <span className="text-muted-foreground">{c.video_count}</span>
                  </button>
                );
              })
            )}
          </div>
          {selectedCollectionId && (
            <div className="border-t p-2">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => { onCollectionChange(""); setOpen(false); }}
                className="h-7 w-full text-xs"
              >
                Clear collection
              </Button>
            </div>
          )}
        </PopoverContent>
      </Popover>
    </div>
  );
}

function LibraryModeContent() {
  const {
    libraryItems,
    processingItems,
    selectedIds,
    selectedCollectionId,
    onSelectionChange,
    onCollectionChange,
    collections,
    isLoading,
  } = useSourcesPanel();

  const [searchTerm, setSearchTerm] = useState("");
  const [addPanelOpen, setAddPanelOpen] = useState(false);
  const [addPanelTab, setAddPanelTab] = useState("url");

  const filteredItems = useMemo(() => {
    if (!searchTerm) return libraryItems;
    const term = searchTerm.toLowerCase();
    return libraryItems.filter(
      (i) =>
        i.title.toLowerCase().includes(term) ||
        i.channel_name?.toLowerCase().includes(term)
    );
  }, [libraryItems, searchTerm]);

  const toggleItem = (id: string) => {
    if (selectedCollectionId) onCollectionChange("");
    onSelectionChange(
      selectedIds.includes(id)
        ? selectedIds.filter((x) => x !== id)
        : [...selectedIds, id]
    );
  };

  const selectAll = () => {
    if (selectedCollectionId) onCollectionChange("");
    onSelectionChange(filteredItems.map((i) => i.id));
  };

  const clearSelection = () => {
    onSelectionChange([]);
    onCollectionChange("");
  };

  return (
    <div className="flex flex-col gap-3 h-full">
      {/* Search */}
      <div className="relative">
        <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
        <Input
          placeholder="Search sources..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="pl-8 h-8 text-xs"
        />
      </div>

      {/* Collections */}
      {collections.length > 0 && (
        <CollectionPicker
          collections={collections}
          selectedCollectionId={selectedCollectionId}
          onCollectionChange={onCollectionChange}
          onSelectionChange={onSelectionChange}
        />
      )}

      {/* Selection controls */}
      {!selectedCollectionId && libraryItems.length > 0 && (
        <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
          <span>{selectedIds.length} selected</span>
          <span>&bull;</span>
          <button onClick={selectAll} className="hover:text-foreground transition-colors">Select all</button>
          <span>&bull;</span>
          <button onClick={clearSelection} className="hover:text-foreground transition-colors">Clear</button>
        </div>
      )}

      {/* Content list */}
      <div className="flex-1 overflow-y-auto -mx-3 px-3 min-h-0">
        {isLoading ? (
          <div className="flex items-center justify-center py-8 text-xs text-muted-foreground">
            <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />
            Loading...
          </div>
        ) : libraryItems.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-8 gap-3 text-center">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10">
              <FileText className="h-5 w-5 text-primary" />
            </div>
            <div className="space-y-1">
              <p className="text-xs font-medium">No content yet</p>
              <p className="text-[11px] text-muted-foreground">Add videos or documents to get started.</p>
            </div>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" className="h-7 text-xs gap-1" onClick={() => { setAddPanelTab("url"); setAddPanelOpen(true); }}>
                <Link2 className="h-3 w-3" />
                Add video
              </Button>
              <Button variant="outline" size="sm" className="h-7 text-xs gap-1" onClick={() => { setAddPanelTab("upload"); setAddPanelOpen(true); }}>
                <Upload className="h-3 w-3" />
                Upload
              </Button>
            </div>
          </div>
        ) : filteredItems.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-8 gap-2 text-center">
            <Search className="h-6 w-6 text-muted-foreground" />
            <p className="text-xs text-muted-foreground">No matching content</p>
          </div>
        ) : (
          <div className="space-y-0.5">
            {filteredItems.map((item) => (
              <LibraryItem
                key={item.id}
                item={item}
                isSelected={selectedIds.includes(item.id)}
                isDisabled={!!selectedCollectionId}
                onToggle={() => toggleItem(item.id)}
              />
            ))}
          </div>
        )}

        {/* Processing section */}
        {processingItems.length > 0 && (
          <div className="mt-3 pt-3 border-t">
            <p className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider mb-2">Processing</p>
            {processingItems.map((item) => (
              <div key={item.id} className="flex items-center gap-2 py-1.5 opacity-50">
                <Loader2 className="h-3.5 w-3.5 animate-spin flex-shrink-0" />
                {item.type === "video" ? (
                  <Video className="h-3.5 w-3.5 flex-shrink-0 text-muted-foreground" />
                ) : (
                  <FileText className="h-3.5 w-3.5 flex-shrink-0 text-muted-foreground" />
                )}
                <span className="text-xs truncate flex-1">{item.title}</span>
                <Badge variant="outline" className="text-[9px] h-4 px-1">{item.status}</Badge>
              </div>
            ))}
          </div>
        )}
      </div>

      <AddContentPanel
        isOpen={addPanelOpen}
        onClose={() => setAddPanelOpen(false)}
        onSuccess={() => setAddPanelOpen(false)}
        defaultTab={addPanelTab}
      />
    </div>
  );
}

function LibraryItem({
  item,
  isSelected,
  isDisabled,
  onToggle,
}: {
  item: LibraryContentItem;
  isSelected: boolean;
  isDisabled: boolean;
  onToggle: () => void;
}) {
  return (
    <label
      className={cn(
        "flex items-center gap-2 rounded-md px-2 py-1.5 cursor-pointer hover:bg-muted/50 transition-colors",
        isSelected && "bg-primary/5"
      )}
    >
      <Checkbox
        checked={isSelected}
        onCheckedChange={onToggle}
        disabled={isDisabled}
        className="h-3.5 w-3.5"
      />
      {item.type === "video" ? (
        <Video className="h-3.5 w-3.5 flex-shrink-0 text-muted-foreground" />
      ) : (
        <FileText className="h-3.5 w-3.5 flex-shrink-0 text-muted-foreground" />
      )}
      <span className="flex-1 text-xs truncate">{item.title}</span>
      <span className="text-[10px] text-muted-foreground whitespace-nowrap">
        {item.type === "video" && item.duration_seconds
          ? formatDuration(item.duration_seconds)
          : item.type === "document" && item.page_count
          ? `${item.page_count} pg`
          : ""}
      </span>
    </label>
  );
}

function ConversationModeContent() {
  const {
    conversationSources,
    selectedSourcesCount,
    totalSourcesCount,
    onToggleSource,
    onSelectAll,
    onDeselectAll,
    sourcesUpdatePending,
    sourcesUpdateError,
    onReprocessSource,
    reprocessPending,
    isLoading,
  } = useSourcesPanel();

  const [filter, setFilter] = useState("");

  const filteredSources = useMemo(() => {
    if (!filter) return conversationSources;
    const term = filter.toLowerCase();
    return conversationSources.filter((s) =>
      (s.title || "Untitled").toLowerCase().includes(term)
    );
  }, [conversationSources, filter]);

  return (
    <div className="flex flex-col gap-3 h-full">
      {/* Header controls */}
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs text-muted-foreground">
            {selectedSourcesCount} of {totalSourcesCount} selected
          </p>
          {sourcesUpdateError && (
            <p className="text-[11px] text-destructive mt-0.5">{sourcesUpdateError}</p>
          )}
        </div>
        <div className="flex gap-1">
          <Button
            variant="ghost"
            size="sm"
            className="h-6 px-2 text-[11px]"
            onClick={onSelectAll}
            disabled={sourcesUpdatePending || conversationSources.length === 0}
          >
            All
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="h-6 px-2 text-[11px]"
            onClick={onDeselectAll}
            disabled={sourcesUpdatePending || conversationSources.length === 0}
          >
            None
          </Button>
        </div>
      </div>

      {/* Filter */}
      {conversationSources.length > 6 && (
        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Filter sources..."
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="pl-8 h-8 text-xs"
          />
        </div>
      )}

      {/* Source list */}
      <div className="flex-1 overflow-y-auto -mx-3 px-3 min-h-0">
        {isLoading ? (
          <div className="flex items-center justify-center py-8 text-xs text-muted-foreground">
            <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />
            Loading sources...
          </div>
        ) : conversationSources.length === 0 ? (
          <p className="text-xs text-muted-foreground text-center py-8">No sources attached.</p>
        ) : (
          <TooltipProvider delayDuration={300}>
            <div className="space-y-0.5">
              {filteredSources.map((source) => (
                <ConversationSourceItem
                  key={source.video_id}
                  source={source}
                  onToggle={() => onToggleSource(source.video_id)}
                  disabled={sourcesUpdatePending}
                  onReprocess={onReprocessSource}
                  reprocessPending={reprocessPending}
                />
              ))}
            </div>
          </TooltipProvider>
        )}
      </div>
    </div>
  );
}

function ConversationSourceItem({
  source,
  onToggle,
  disabled,
  onReprocess,
  reprocessPending,
}: {
  source: ConversationSource;
  onToggle: () => void;
  disabled: boolean;
  onReprocess?: (videoId: string) => void;
  reprocessPending?: boolean;
}) {
  return (
    <label
      className={cn(
        "flex items-start gap-2 rounded-md px-2 py-1.5 cursor-pointer hover:bg-muted/50 transition-colors",
        source.is_selected && "bg-primary/5"
      )}
    >
      <Checkbox
        checked={source.is_selected}
        onCheckedChange={onToggle}
        disabled={disabled || source.selectable === false}
        className="h-3.5 w-3.5 mt-0.5"
      />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1.5">
          {source.content_type && source.content_type !== "youtube" ? (
            <FileText className="h-3.5 w-3.5 flex-shrink-0 text-muted-foreground" />
          ) : (
            <Video className="h-3.5 w-3.5 flex-shrink-0 text-muted-foreground" />
          )}
          <Tooltip>
            <TooltipTrigger asChild>
              <span className="text-xs truncate">{source.title || "Untitled"}</span>
            </TooltipTrigger>
            <TooltipContent side="left" className="max-w-xs">
              <p className="text-xs">{source.title || "Untitled"}</p>
            </TooltipContent>
          </Tooltip>
          {source.status && source.status !== "completed" && (
            <Badge variant="outline" className="text-[9px] h-4 px-1 shrink-0">{source.status}</Badge>
          )}
        </div>
        <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground ml-5">
          {source.duration_seconds ? <span>{formatDuration(source.duration_seconds)}</span> : null}
          {source.added_via && <span>via {source.added_via}</span>}
        </div>
        {source.selectable === false && (
          <div className="flex items-center gap-2 text-[10px] text-destructive ml-5 mt-0.5">
            <span className="truncate">{source.selectable_reason}</span>
            {!source.is_deleted && onReprocess && (
              <Button
                type="button"
                size="sm"
                variant="outline"
                className="h-5 px-1.5 text-[10px]"
                onClick={(e) => { e.preventDefault(); e.stopPropagation(); onReprocess(source.video_id); }}
                disabled={reprocessPending}
              >
                Reprocess
              </Button>
            )}
          </div>
        )}
      </div>
    </label>
  );
}

function PanelContent() {
  const { mode, isPanelOpen, togglePanel } = useSourcesPanel();
  const [addPanelOpen, setAddPanelOpen] = useState(false);

  return (
    <div className="flex flex-col h-full">
      {/* Panel header */}
      <div className="flex items-center justify-between px-3 py-2.5 border-b">
        <h2 className="text-sm font-medium">Sources</h2>
        <div className="flex items-center gap-1">
          {mode === "library" && (
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7"
              onClick={() => setAddPanelOpen(true)}
              title="Add content"
            >
              <Plus className="h-4 w-4" />
            </Button>
          )}
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7"
            onClick={togglePanel}
            title="Collapse panel"
          >
            <PanelRightClose className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* Panel body */}
      <div className="flex-1 overflow-hidden px-3 py-3 min-h-0">
        {mode === "library" ? <LibraryModeContent /> : <ConversationModeContent />}
      </div>

      {mode === "library" && (
        <AddContentPanel
          isOpen={addPanelOpen}
          onClose={() => setAddPanelOpen(false)}
          onSuccess={() => setAddPanelOpen(false)}
          defaultTab="url"
        />
      )}
    </div>
  );
}

// Shared mobile sheet state — managed outside context so it doesn't conflict with desktop panel
let mobileSheetOpenCallback: ((open: boolean) => void) | null = null;

export function SourcesPanel() {
  const { isPanelOpen, togglePanel } = useSourcesPanel();
  const [mobileSheetOpen, setMobileSheetOpen] = useState(false);

  // Register callback so SourcesPanelToggle can open the mobile sheet
  useEffect(() => {
    mobileSheetOpenCallback = setMobileSheetOpen;
    return () => { mobileSheetOpenCallback = null; };
  }, []);

  return (
    <>
      {/* Desktop: side panel */}
      <aside
        className={cn(
          "hidden lg:flex flex-col border-l bg-background transition-all duration-200",
          isPanelOpen ? "w-72" : "w-10"
        )}
      >
        {isPanelOpen ? (
          <PanelContent />
        ) : (
          <button
            onClick={togglePanel}
            className="flex flex-col items-center pt-3 gap-2 w-full hover:bg-muted/50 transition-colors h-full"
            title="Expand sources panel"
          >
            <PanelRightOpen className="h-4 w-4 text-muted-foreground" />
            <span className="text-[10px] text-muted-foreground [writing-mode:vertical-lr] rotate-180">
              Sources
            </span>
          </button>
        )}
      </aside>

      {/* Mobile/Tablet: Sheet from right */}
      <div className="lg:hidden">
        <Sheet open={mobileSheetOpen} onOpenChange={setMobileSheetOpen}>
          <SheetContent side="right" className="w-full max-w-sm p-0">
            <PanelContent />
          </SheetContent>
        </Sheet>
      </div>
    </>
  );
}

/** Toggle button for header (shown on < lg screens) */
export function SourcesPanelToggle() {
  const { mode, selectedSourcesCount, totalSourcesCount, selectedIds, selectedCollectionId } = useSourcesPanel();

  const count = mode === "conversation"
    ? `${selectedSourcesCount}/${totalSourcesCount}`
    : selectedCollectionId
    ? "1 collection"
    : selectedIds.length > 0
    ? `${selectedIds.length} selected`
    : "0";

  return (
    <Button
      variant="ghost"
      size="sm"
      className="h-8 gap-1.5 text-xs lg:hidden"
      onClick={() => mobileSheetOpenCallback?.(true)}
      title="Toggle sources panel"
    >
      <PanelRightOpen className="h-4 w-4" />
      <span className="hidden sm:inline">Sources</span>
      <Badge variant="secondary" className="px-1.5 py-0 text-[10px]">
        {count}
      </Badge>
    </Button>
  );
}
