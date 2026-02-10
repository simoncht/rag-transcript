"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { conversationsApi } from "@/lib/api/conversations";
import { EllipsisVertical, Pencil, Trash2, Download } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

interface ExportableMessage {
  role: string;
  content: string;
  chunks_retrieved_count?: number;
  response_time_seconds?: number;
}

interface ConversationActionsMenuProps {
  conversationId: string;
  currentTitle: string;
  variant?: "compact" | "default" | "list";
  messages?: ExportableMessage[];
  sourceCount?: number;
  onRenameStart?: () => void;
  onDeleted?: () => void;
}

export function ConversationActionsMenu({
  conversationId,
  currentTitle,
  variant = "default",
  messages,
  sourceCount,
  onRenameStart,
  onDeleted,
}: ConversationActionsMenuProps) {
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const queryClient = useQueryClient();

  const deleteMutation = useMutation({
    mutationFn: () => conversationsApi.delete(conversationId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["conversations"] });
      setDeleteDialogOpen(false);
      onDeleted?.();
    },
  });

  const handleExport = () => {
    if (!messages) return;
    const userMessages = messages.filter((m) => m.role !== "system");
    const lines = [
      `# ${currentTitle}`,
      "",
      `**Sources:** ${sourceCount ?? "unknown"} sources`,
      `**Messages:** ${userMessages.length}`,
      `**Exported:** ${new Date().toLocaleDateString()}`,
      "",
      "---",
      "",
    ];
    for (const msg of userMessages) {
      const role = msg.role === "user" ? "You" : "Assistant";
      lines.push(`**${role}:** ${msg.content}`);
      if (msg.role === "assistant") {
        const meta: string[] = [];
        if (msg.chunks_retrieved_count != null) meta.push(`${msg.chunks_retrieved_count} chunks`);
        if (msg.response_time_seconds != null) meta.push(`${msg.response_time_seconds.toFixed(1)}s`);
        if (meta.length > 0) lines.push(`[Sources: ${meta.join(", ")}]`);
      }
      lines.push("", "---", "");
    }
    const markdown = lines.join("\n");
    const slug = currentTitle.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");
    const blob = new Blob([markdown], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${slug || "conversation"}-export.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const triggerSize =
    variant === "compact"
      ? "h-6 w-6"
      : "h-8 w-8";

  const iconSize =
    variant === "compact"
      ? "h-4 w-4"
      : "h-4 w-4";

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant="ghost"
            size="icon"
            className={`${triggerSize} shrink-0`}
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
            }}
          >
            <EllipsisVertical className={iconSize} />
            <span className="sr-only">Conversation actions</span>
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" onClick={(e) => e.stopPropagation()}>
          <DropdownMenuItem
            onClick={(e) => {
              e.stopPropagation();
              onRenameStart?.();
            }}
          >
            <Pencil className="mr-2 h-4 w-4" />
            Rename
          </DropdownMenuItem>
          {messages && (
            <DropdownMenuItem
              onClick={(e) => {
                e.stopPropagation();
                handleExport();
              }}
            >
              <Download className="mr-2 h-4 w-4" />
              Export
            </DropdownMenuItem>
          )}
          <DropdownMenuItem
            className="text-destructive focus:text-destructive"
            onClick={(e) => {
              e.stopPropagation();
              setDeleteDialogOpen(true);
            }}
          >
            <Trash2 className="mr-2 h-4 w-4" />
            Delete
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <DialogContent onClick={(e) => e.stopPropagation()}>
          <DialogHeader>
            <DialogTitle>Delete conversation</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete &ldquo;{currentTitle}&rdquo;? This
              action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setDeleteDialogOpen(false)}
              disabled={deleteMutation.isPending}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={() => deleteMutation.mutate()}
              disabled={deleteMutation.isPending}
            >
              {deleteMutation.isPending ? "Deleting..." : "Delete"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
