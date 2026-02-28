"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";
import { formatDistanceToNow } from "date-fns";
import { ConversationInsightMap } from "@/components/insights/ConversationInsightMap";
import { MemoryBadge } from "@/components/conversations/MemoryPanel";
import { ConversationActionsMenu } from "@/components/conversations/ConversationActionsMenu";
import { InlineRenameInput } from "@/components/conversations/InlineRenameInput";
import { ThemeToggle } from "@/components/layout/ThemeToggle";
import { SourcesPanelToggle } from "./SourcesPanel";
import {
  Menu,
  Network,
  RotateCcw,
  Maximize2,
  Minimize2,
  Loader2,
} from "lucide-react";
import type {
  Message,
  ConversationWithMessages,
  ConversationInsightsResponse,
} from "@/lib/types";

export interface ChatHeaderProps {
  conversation: ConversationWithMessages;
  conversationId: string;
  messages: Message[];
  // Source counts (for display)
  selectedSourcesCount: number;
  totalSourcesCount: number;
  // Insights
  insightsData?: ConversationInsightsResponse | null;
  insightsLoading: boolean;
  insightsError: boolean;
  insightsDialogOpen: boolean;
  onInsightsDialogChange: (open: boolean) => void;
  onRegenerateInsights: () => void;
  regenerateInsightsPending: boolean;
  // Sidebar toggle (mobile)
  sidebarOpen: boolean;
  onToggleSidebar: () => void;
  // Actions
  onConversationDeleted: () => void;
  onNavigateBack: () => void;
}

export function ChatHeader({
  conversation,
  conversationId,
  messages,
  selectedSourcesCount,
  totalSourcesCount,
  insightsData,
  insightsLoading,
  insightsError,
  insightsDialogOpen,
  onInsightsDialogChange,
  onRegenerateInsights,
  regenerateInsightsPending,
  onToggleSidebar,
  onConversationDeleted,
}: ChatHeaderProps) {
  const [isRenamingHeader, setIsRenamingHeader] = useState(false);
  const [insightsDialogMaximized, setInsightsDialogMaximized] = useState(false);

  return (
    <header className="sticky top-0 z-30 border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="flex h-16 items-center px-4">
        <div className="flex flex-1 flex-col justify-center gap-0.5">
          {/* Primary: Title with mobile menu */}
          <div className="flex items-center gap-3">
            <Button
              variant="ghost"
              size="icon"
              className="h-9 w-9 lg:hidden"
              onClick={onToggleSidebar}
            >
              <Menu className="h-5 w-5" />
            </Button>
            <Separator orientation="vertical" className="h-6 lg:hidden" />
            {isRenamingHeader ? (
              <InlineRenameInput
                conversationId={conversationId}
                currentTitle={conversation.title || "New conversation"}
                onComplete={() => setIsRenamingHeader(false)}
                className="h-8 max-w-xs text-sm"
              />
            ) : (
              <h1 className="text-sm font-medium truncate">
                {conversation.title || "New conversation"}
              </h1>
            )}
            <ConversationActionsMenu
              conversationId={conversationId}
              currentTitle={conversation.title || "New conversation"}
              variant="default"
              messages={messages}
              sourceCount={selectedSourcesCount}
              onRenameStart={() => setIsRenamingHeader(true)}
              onDeleted={onConversationDeleted}
            />
          </div>

          {/* Secondary: Metadata */}
          <div className="flex items-center gap-2 text-xs text-muted-foreground ml-10 lg:ml-0">
            <span>
              {selectedSourcesCount} of {totalSourcesCount} source
              {totalSourcesCount !== 1 ? "s" : ""}
            </span>
            <span>&bull;</span>
            <span>
              {conversation.message_count || messages.length} message
              {(conversation.message_count || messages.length) !== 1 ? "s" : ""}
            </span>
            {conversation.last_message_at && (
              <>
                <span>&bull;</span>
                <span>
                  Active {formatDistanceToNow(new Date(conversation.last_message_at), { addSuffix: true })}
                </span>
              </>
            )}
            <MemoryBadge
              conversationId={conversationId}
              messageCount={conversation.message_count || messages.length}
            />
          </div>
        </div>
        <div className="flex items-center gap-2">
          {/* Insights dialog */}
          <Dialog
            open={insightsDialogOpen}
            onOpenChange={(open) => {
              onInsightsDialogChange(open);
              if (!open) setInsightsDialogMaximized(false);
            }}
          >
            <DialogTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                className="h-9 w-9"
                disabled={selectedSourcesCount === 0}
                title={
                  selectedSourcesCount === 0
                    ? "Select at least one source to generate insights"
                    : "Generate a topic map from selected video sources"
                }
              >
                <Network className="h-4 w-4" />
              </Button>
            </DialogTrigger>
            <DialogContent
              className={cn(
                "p-0 flex flex-col gap-0",
                insightsDialogMaximized
                  ? "max-w-[calc(100vw-1.5rem)] h-[calc(100vh-1.5rem)]"
                  : "max-w-6xl h-[85vh]"
              )}
            >
              <DialogHeader className="p-6 pb-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <DialogTitle>Conversation Insights: Topic Map</DialogTitle>
                    {insightsData?.metadata ? (
                      <p className="mt-1 text-xs text-muted-foreground">
                        {insightsData.metadata.cached ? "Cached" : "Generated"} &bull;{" "}
                        {insightsData.metadata.topics_count} topics
                      </p>
                    ) : null}
                  </div>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      className="gap-2"
                      onClick={() => setInsightsDialogMaximized((prev) => !prev)}
                      title={insightsDialogMaximized ? "Restore window" : "Enlarge window"}
                    >
                      {insightsDialogMaximized ? (
                        <Minimize2 className="h-4 w-4" />
                      ) : (
                        <Maximize2 className="h-4 w-4" />
                      )}
                      {insightsDialogMaximized ? "Restore" : "Enlarge"}
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      className="gap-2"
                      onClick={onRegenerateInsights}
                      disabled={regenerateInsightsPending || insightsLoading || !conversationId}
                    >
                      {regenerateInsightsPending ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <RotateCcw className="h-4 w-4" />
                      )}
                      Regenerate
                    </Button>
                  </div>
                </div>
              </DialogHeader>
              <div className="flex-1 min-h-0 px-6 pb-6">
                {insightsLoading || regenerateInsightsPending ? (
                  <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Generating insights...
                  </div>
                ) : insightsError ? (
                  <div className="flex h-full items-center justify-center text-sm text-destructive">
                    Failed to load insights.
                  </div>
                ) : insightsData ? (
                  <ConversationInsightMap
                    conversationId={conversationId}
                    graphData={insightsData.graph}
                  />
                ) : (
                  <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
                    No insights available.
                  </div>
                )}
              </div>
            </DialogContent>
          </Dialog>

          <ThemeToggle />

          {/* Sources panel toggle — visible on < lg */}
          <SourcesPanelToggle />
        </div>
      </div>
    </header>
  );
}
