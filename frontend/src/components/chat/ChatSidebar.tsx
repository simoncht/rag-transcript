"use client";

import Link from "next/link";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import {
  MessageCircle,
  Plus,
  Video,
  FileText,
  Folder,
  User,
  Shield,
  LogOut,
  X,
} from "lucide-react";
import { ConversationActionsMenu } from "@/components/conversations/ConversationActionsMenu";
import { InlineRenameInput } from "@/components/conversations/InlineRenameInput";
import type { Conversation, QuotaUsage } from "@/lib/types";
import { useState } from "react";

export interface ChatSidebarProps {
  conversations: Conversation[];
  activeConversationId?: string;
  sidebarOpen: boolean;
  onCloseSidebar: () => void;
  hasAdminAccess: boolean;
  user: {
    displayName?: string | null;
    email?: string | null;
  } | null;
  quota: QuotaUsage | null;
  onLogout: () => void;
  onConversationDeleted?: (deletedId: string) => string | null;
}

export function ChatSidebar({
  conversations,
  activeConversationId,
  sidebarOpen,
  onCloseSidebar,
  hasAdminAccess,
  user,
  quota,
  onLogout,
  onConversationDeleted,
}: ChatSidebarProps) {
  const [renamingSidebarId, setRenamingSidebarId] = useState<string | null>(null);
  const displayName = user?.displayName || user?.email;
  const email = user?.email;

  return (
    <>
      <div
        className={cn(
          "fixed inset-y-0 left-0 z-50 w-64 transform border-r bg-background transition-transform duration-200 ease-in-out lg:relative lg:translate-x-0",
          sidebarOpen ? "translate-x-0" : "-translate-x-full"
        )}
      >
        <div className="flex h-full flex-col">
          {/* Sidebar header */}
          <div className="flex h-14 items-center justify-between border-b px-3">
            <Link href="/chat" className="flex items-center gap-2">
              <div className="flex h-7 w-7 items-center justify-center rounded-md bg-primary text-primary-foreground">
                <span className="text-xs font-bold">RT</span>
              </div>
              <span className="text-sm font-semibold">RAG Transcript</span>
            </Link>
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8 lg:hidden"
              onClick={onCloseSidebar}
            >
              <X className="h-4 w-4" />
            </Button>
          </div>

          {/* New chat button */}
          <div className="p-3">
            <Link href="/chat">
              <Button variant="outline" className="w-full justify-start gap-2" size="sm">
                <Plus className="h-4 w-4" />
                New chat
              </Button>
            </Link>
          </div>

          {/* Recent conversations */}
          <div className="flex-1 overflow-y-auto px-3 py-3">
            <p className="mb-2 px-2 text-xs font-medium text-muted-foreground">Recent</p>
            {conversations.length === 0 ? (
              <p className="px-2 text-xs text-muted-foreground">No conversations yet</p>
            ) : (
              <div className="space-y-0.5">
                {conversations.slice(0, 20).map((conv: Conversation) => (
                  <div key={conv.id} className="group relative">
                    <Link href={`/chat/${conv.id}`}>
                      <Button
                        variant="ghost"
                        className={cn(
                          "w-full justify-start gap-2 text-sm h-9 pr-8",
                          conv.id === activeConversationId && "bg-muted"
                        )}
                      >
                        <MessageCircle className="h-4 w-4 flex-shrink-0 text-muted-foreground" />
                        {renamingSidebarId === conv.id ? (
                          <InlineRenameInput
                            conversationId={conv.id}
                            currentTitle={conv.title || "Untitled"}
                            onComplete={() => setRenamingSidebarId(null)}
                            className="h-6 text-sm"
                          />
                        ) : (
                          <span className="truncate">{conv.title || "Untitled"}</span>
                        )}
                      </Button>
                    </Link>
                    {renamingSidebarId !== conv.id && (
                      <div className="absolute right-1 top-1/2 -translate-y-1/2 opacity-0 group-hover:opacity-100 transition-opacity">
                        <ConversationActionsMenu
                          conversationId={conv.id}
                          currentTitle={conv.title || "Untitled"}
                          variant="compact"
                          onRenameStart={() => setRenamingSidebarId(conv.id)}
                          onDeleted={() => {
                            if (conv.id === activeConversationId && onConversationDeleted) {
                              onConversationDeleted(conv.id);
                            }
                          }}
                        />
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Navigation */}
          <nav className="border-t px-3 py-3">
            <p className="mb-2 px-2 text-xs font-medium text-muted-foreground">Navigate</p>
            <div className="space-y-0.5">
              <Link href="/videos">
                <Button
                  variant="ghost"
                  className="w-full justify-start gap-2 text-sm h-9 text-muted-foreground hover:text-foreground"
                >
                  <Video className="h-4 w-4" />
                  Videos
                </Button>
              </Link>
              <Link href="/documents">
                <Button
                  variant="ghost"
                  className="w-full justify-start gap-2 text-sm h-9 text-muted-foreground hover:text-foreground"
                >
                  <FileText className="h-4 w-4" />
                  Documents
                </Button>
              </Link>
              <Link href="/collections">
                <Button
                  variant="ghost"
                  className="w-full justify-start gap-2 text-sm h-9 text-muted-foreground hover:text-foreground"
                >
                  <Folder className="h-4 w-4" />
                  Collections
                </Button>
              </Link>
              <Link href="/account">
                <Button
                  variant="ghost"
                  className="w-full justify-start gap-2 text-sm h-9 text-muted-foreground hover:text-foreground"
                >
                  <User className="h-4 w-4" />
                  Account
                </Button>
              </Link>
              {hasAdminAccess && (
                <Link href="/admin">
                  <Button
                    variant="ghost"
                    className="w-full justify-start gap-2 text-sm h-9 text-muted-foreground hover:text-foreground"
                  >
                    <Shield className="h-4 w-4" />
                    Admin
                  </Button>
                </Link>
              )}
            </div>
          </nav>

          {/* Compact footer: Quota + User avatar */}
          <div className="border-t px-3 py-2">
            <div className="flex items-center justify-between">
              {/* Quota indicator */}
              {quota && (
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Link href="/account" className="flex items-center gap-2 text-xs text-muted-foreground hover:text-foreground transition-colors">
                        <div className="h-2 w-16 rounded-full bg-muted overflow-hidden">
                          <div
                            className="h-full bg-primary transition-all"
                            style={{
                              width: quota.videos_limit === -1
                                ? '10%'
                                : `${Math.min((quota.videos_used / quota.videos_limit) * 100, 100)}%`,
                            }}
                          />
                        </div>
                        <span>
                          {quota.videos_used}/{quota.videos_limit === -1 ? '\u221e' : quota.videos_limit}
                        </span>
                      </Link>
                    </TooltipTrigger>
                    <TooltipContent side="top">
                      <p className="text-xs">
                        Videos: {quota.videos_used}/{quota.videos_limit === -1 ? '\u221e' : quota.videos_limit}
                      </p>
                      <p className="text-xs">
                        Messages: {quota.messages_used}/{quota.messages_limit === -1 ? '\u221e' : quota.messages_limit}/mo
                      </p>
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              )}

              {/* User avatar with dropdown */}
              {user && (
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button variant="ghost" size="icon" className="h-8 w-8 rounded-full">
                      <div className="h-7 w-7 rounded-full bg-primary/10 flex items-center justify-center">
                        <span className="text-xs font-medium">
                          {displayName?.charAt(0)?.toUpperCase() || "U"}
                        </span>
                      </div>
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end" className="w-48">
                    <DropdownMenuLabel className="font-normal">
                      <div className="flex flex-col space-y-1">
                        <p className="text-sm font-medium leading-none">{displayName}</p>
                        {email && (
                          <p className="text-xs leading-none text-muted-foreground truncate">
                            {email}
                          </p>
                        )}
                      </div>
                    </DropdownMenuLabel>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem asChild>
                      <Link href="/account" className="cursor-pointer">
                        <User className="mr-2 h-4 w-4" />
                        Account
                      </Link>
                    </DropdownMenuItem>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem onClick={onLogout} className="cursor-pointer">
                      <LogOut className="mr-2 h-4 w-4" />
                      Logout
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Overlay for mobile */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 lg:hidden"
          onClick={onCloseSidebar}
        />
      )}
    </>
  );
}
