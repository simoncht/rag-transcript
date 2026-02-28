"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api/client";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { Brain, Trash2, Loader2 } from "lucide-react";

interface Fact {
  id: string;
  fact_key: string;
  fact_value: string;
  confidence_score: number;
  importance: number;
  category: string;
  access_count: number;
  source_turn: number;
  created_at: string | null;
  last_accessed: string | null;
}

interface FactsResponse {
  total: number;
  facts_by_category: Record<string, Fact[]>;
}

interface MemoryPanelProps {
  conversationId: string;
}

const CATEGORY_LABELS: Record<string, string> = {
  identity: "Identity",
  topic: "Topics",
  preference: "Preferences",
  session: "Session",
  ephemeral: "Ephemeral",
};

export function MemoryPanel({ conversationId }: MemoryPanelProps) {
  const [open, setOpen] = useState(false);
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery<FactsResponse>({
    queryKey: ["conversation-facts", conversationId],
    queryFn: async () => {
      const res = await apiClient.get(`/conversations/${conversationId}/facts`);
      return res.data;
    },
    enabled: open,
    staleTime: 30_000,
  });

  const deleteFact = useMutation({
    mutationFn: async (factId: string) => {
      await apiClient.delete(`/conversations/${conversationId}/facts/${factId}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["conversation-facts", conversationId] });
    },
  });

  const clearAllFacts = useMutation({
    mutationFn: async () => {
      await apiClient.delete(`/conversations/${conversationId}/facts`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["conversation-facts", conversationId] });
    },
  });

  const totalFacts = data?.total ?? 0;

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild>
        <button
          className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
          title="View conversation memory"
        >
          <Brain className="h-3.5 w-3.5" />
          {totalFacts > 0 && <span>{totalFacts} facts</span>}
        </button>
      </SheetTrigger>
      <SheetContent side="right" className="w-full max-w-md overflow-y-auto">
        <SheetHeader>
          <SheetTitle className="flex items-center gap-2">
            <Brain className="h-5 w-5" />
            Conversation Memory
          </SheetTitle>
          <p className="text-xs text-muted-foreground">
            Key facts learned from this conversation to improve future responses.
          </p>
        </SheetHeader>

        <div className="mt-4 space-y-4">
          {isLoading ? (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading memory...
            </div>
          ) : totalFacts === 0 ? (
            <p className="text-sm text-muted-foreground">
              No facts extracted yet. Memory is activated after 15+ messages.
            </p>
          ) : (
            <>
              {Object.entries(data?.facts_by_category ?? {}).map(([category, facts]) => (
                <div key={category} className="space-y-2">
                  <h3 className="text-sm font-medium">
                    {CATEGORY_LABELS[category] || category}
                  </h3>
                  {facts.map((fact) => (
                    <div
                      key={fact.id}
                      className="rounded-md border bg-background/60 px-3 py-2 text-xs"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="flex-1 space-y-1">
                          <p className="text-foreground leading-relaxed">
                            {fact.fact_value}
                          </p>
                          <div className="flex flex-wrap items-center gap-2 text-[10px] text-muted-foreground">
                            <span>
                              Confidence: {Math.round(fact.confidence_score * 100)}%
                            </span>
                            {fact.access_count > 0 && (
                              <span>Accessed {fact.access_count} time{fact.access_count !== 1 ? "s" : ""}</span>
                            )}
                          </div>
                        </div>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-6 w-6 text-muted-foreground hover:text-destructive"
                          onClick={() => deleteFact.mutate(fact.id)}
                          disabled={deleteFact.isPending}
                        >
                          <Trash2 className="h-3 w-3" />
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              ))}
              <Button
                variant="outline"
                size="sm"
                className="w-full text-xs gap-2"
                onClick={() => clearAllFacts.mutate()}
                disabled={clearAllFacts.isPending}
              >
                {clearAllFacts.isPending ? (
                  <Loader2 className="h-3 w-3 animate-spin" />
                ) : (
                  <Trash2 className="h-3 w-3" />
                )}
                Clear all memory
              </Button>
            </>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}

/** Badge shown in conversation header when facts exist */
export function MemoryBadge({ conversationId, messageCount }: { conversationId: string; messageCount: number }) {
  // Only show for conversations with enough messages for fact extraction
  if (messageCount < 15) return null;

  return (
    <MemoryPanel conversationId={conversationId} />
  );
}
