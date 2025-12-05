"use client";

import { useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import ReactMarkdown from "react-markdown";
import { conversationsApi } from "@/lib/api/conversations";
import type { ConversationWithMessages, Message, ChunkReference } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import {
  ArrowLeft,
  Loader2,
  MessageCircle,
  Menu,
  PanelLeftClose,
  PanelLeft,
  Plus,
  Video,
  Folder,
  X,
} from "lucide-react";
import Link from "next/link";
import { ThemeToggle } from "@/components/layout/ThemeToggle";
import type { Conversation } from "@/lib/types";

export default function ConversationDetailPage() {
  const params = useParams();
  const router = useRouter();
  const conversationId = Array.isArray(params?.id) ? params.id[0] : (params?.id as string | undefined);

  const queryClient = useQueryClient();
  const [messageText, setMessageText] = useState("");
  const [isAutoScrollEnabled, setIsAutoScrollEnabled] = useState(true);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  // Fetch recent conversations for sidebar
  const { data: conversationsData } = useQuery({
    queryKey: ["conversations"],
    queryFn: () => conversationsApi.list(),
    refetchInterval: 10000,
  });

  const conversations = conversationsData?.conversations ?? [];

  const {
    data: conversation,
    isLoading,
    isError,
  } = useQuery<ConversationWithMessages>({
    queryKey: ["conversation", conversationId],
    queryFn: () => conversationsApi.get(conversationId as string),
    enabled: !!conversationId,
    refetchInterval: 5000,
  });

  const sendMessageMutation = useMutation({
    mutationFn: async (text: string) => {
      if (!conversationId) return;
      const response = await conversationsApi.sendMessage(conversationId, text, false);

      // Optimistically append the assistant message to the conversation cache
      queryClient.setQueryData<ConversationWithMessages | undefined>(
        ["conversation", conversationId],
        (prev) =>
          prev
            ? {
                ...prev,
                messages: [
                  ...prev.messages,
                  {
                    id: response.message_id,
                    conversation_id: response.conversation_id,
                    role: "assistant",
                    content: response.content,
                    token_count: response.token_count,
                    chunks_retrieved_count: response.chunk_references?.length ?? undefined,
                    response_time_seconds: response.response_time_seconds,
                    created_at: new Date().toISOString(),
                    // Attach chunk_references so the sources panel can render.
                    // This extends the Message type locally without changing shared types.
                    chunk_references: response.chunk_references,
                  } as Message & { chunk_references?: ChunkReference[] },
                ],
              }
            : prev,
      );

      return response;
    },
    onSuccess: () => {
      setMessageText("");
      queryClient.invalidateQueries({ queryKey: ["conversation", conversationId] });
    },
  });

  useEffect(() => {
    if (isAutoScrollEnabled && messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: "smooth", block: "end" });
    }
  }, [conversation?.messages?.length, isAutoScrollEnabled]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!messageText.trim() || sendMessageMutation.isPending || !conversationId) {
      return;
    }
    sendMessageMutation.mutate(messageText.trim());
  };

  const handleBack = () => {
    router.push("/conversations");
  };

  if (!conversationId) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <div className="flex flex-col items-center justify-center gap-3 text-center">
          <p className="text-sm font-medium text-destructive">Conversation not found</p>
          <Button variant="outline" size="sm" onClick={handleBack}>
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to conversations
          </Button>
        </div>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <div className="flex items-center text-muted-foreground">
          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          Loading conversation...
        </div>
      </div>
    );
  }

  if (isError || !conversation) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <div className="flex flex-col items-center justify-center gap-3 text-center">
          <p className="text-sm font-medium text-destructive">Unable to load conversation</p>
          <p className="text-xs text-muted-foreground">
            Please check your connection or try again from the conversations page.
          </p>
          <Button variant="outline" size="sm" onClick={handleBack}>
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to conversations
          </Button>
        </div>
      </div>
    );
  }

  const messages = conversation.messages ?? [];

  return (
    <div className="flex min-h-screen bg-background">
      {/* Sidebar - ChatGPT style */}
      <div
        className={cn(
          "fixed inset-y-0 left-0 z-50 w-64 transform border-r bg-background transition-transform duration-200 ease-in-out lg:relative lg:translate-x-0",
          sidebarOpen ? "translate-x-0" : "-translate-x-full"
        )}
      >
        <div className="flex h-full flex-col">
          {/* Sidebar header */}
          <div className="flex h-14 items-center justify-between border-b px-3">
            <Link href="/conversations" className="flex items-center gap-2">
              <div className="flex h-7 w-7 items-center justify-center rounded-md bg-primary text-primary-foreground">
                <span className="text-xs font-bold">RT</span>
              </div>
              <span className="text-sm font-semibold">RAG Transcript</span>
            </Link>
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8 lg:hidden"
              onClick={() => setSidebarOpen(false)}
            >
              <X className="h-4 w-4" />
            </Button>
          </div>

          {/* New chat button */}
          <div className="p-3">
            <Link href="/conversations">
              <Button variant="outline" className="w-full justify-start gap-2" size="sm">
                <Plus className="h-4 w-4" />
                New chat
              </Button>
            </Link>
          </div>

          {/* Recent conversations */}
          <div className="flex-1 overflow-y-auto px-2">
            <div className="space-y-1">
              {conversations.map((conv: Conversation) => (
                <Link key={conv.id} href={`/conversations/${conv.id}`}>
                  <Button
                    variant="ghost"
                    className={cn(
                      "w-full justify-start gap-2 text-xs",
                      conv.id === conversationId && "bg-muted"
                    )}
                    size="sm"
                  >
                    <MessageCircle className="h-3.5 w-3.5 flex-shrink-0" />
                    <span className="truncate">{conv.title || "Untitled"}</span>
                  </Button>
                </Link>
              ))}
            </div>
          </div>

          {/* Navigation */}
          <div className="border-t p-2">
            <Link href="/videos">
              <Button variant="ghost" className="w-full justify-start gap-2" size="sm">
                <Video className="h-4 w-4" />
                Videos
              </Button>
            </Link>
            <Link href="/collections">
              <Button variant="ghost" className="w-full justify-start gap-2" size="sm">
                <Folder className="h-4 w-4" />
                Collections
              </Button>
            </Link>
          </div>
        </div>
      </div>

      {/* Overlay for mobile */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Main content */}
      <div className="flex min-h-screen flex-1 flex-col">
        {/* Top navigation bar - ChatGPT style */}
        <header className="sticky top-0 z-30 border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
          <div className="flex h-14 items-center px-4">
            <div className="flex flex-1 items-center gap-3">
              <Button
                variant="ghost"
                size="icon"
                className="h-9 w-9"
                onClick={() => setSidebarOpen(!sidebarOpen)}
              >
                <Menu className="h-5 w-5" />
              </Button>
              <Separator orientation="vertical" className="h-6" />
              <h1 className="text-sm font-medium truncate">
                {conversation.title || "New conversation"}
              </h1>
            </div>
            <div className="flex items-center gap-2">
              <ThemeToggle />
            </div>
          </div>
        </header>

        {/* Messages area - centered like ChatGPT */}
        <div className="flex-1 overflow-y-auto">
          <div className="mx-auto max-w-3xl px-4 py-6">
            {messages.length === 0 ? (
              <div className="flex h-[60vh] flex-col items-center justify-center gap-3 text-center">
                <div className="flex h-12 w-12 items-center justify-center rounded-full bg-primary/10">
                  <MessageCircle className="h-6 w-6 text-primary" />
                </div>
                <div className="space-y-1">
                  <p className="text-sm font-medium">Start a conversation</p>
                  <p className="text-xs text-muted-foreground">
                    Ask questions about your {conversation.selected_video_ids.length} video
                    {conversation.selected_video_ids.length !== 1 ? "s" : ""}
                  </p>
                </div>
              </div>
            ) : (
              <div className="space-y-6">
                {messages.map((message) => {
                  const isUser = message.role === "user";
                  const withChunks = message as Message & {
                    chunk_references?: ChunkReference[];
                  };
                  const chunkReferences = withChunks.chunk_references;

                  return (
                    <div key={message.id} className="group">
                      {/* Message header with avatar */}
                      <div className="mb-2 flex items-center gap-3">
                        <div
                          className={cn(
                            "flex h-7 w-7 items-center justify-center rounded-full text-xs font-semibold",
                            isUser
                              ? "bg-primary text-primary-foreground"
                              : "bg-primary/10 text-primary",
                          )}
                        >
                          {isUser ? "You" : "ML"}
                        </div>
                        <div className="flex items-center gap-2 text-xs text-muted-foreground">
                          <span className="font-medium">
                            {isUser ? "You" : "Mindful Learning"}
                          </span>
                          <span>·</span>
                          <span>
                            {new Date(message.created_at).toLocaleTimeString([], {
                              hour: "2-digit",
                              minute: "2-digit",
                            })}
                          </span>
                        </div>
                      </div>

                      {/* Message content */}
                      <div className="ml-10">
                        <div className="space-y-3">
                          {isUser ? (
                            <p className="whitespace-pre-wrap break-words text-sm">
                              {message.content}
                            </p>
                          ) : (
                            <ReactMarkdown className="prose prose-sm max-w-none dark:prose-invert">
                              {message.content}
                            </ReactMarkdown>
                          )}

                          {/* Metadata for assistant messages */}
                          {!isUser && (
                            <div className="flex flex-wrap items-center gap-3 text-[11px] text-muted-foreground">
                              {message.response_time_seconds != null && (
                                <span>{message.response_time_seconds.toFixed(1)}s</span>
                              )}
                              {message.chunks_retrieved_count != null && (
                                <span>
                                  {message.chunks_retrieved_count} source
                                  {message.chunks_retrieved_count !== 1 ? "s" : ""}
                                </span>
                              )}
                              {message.token_count != null && (
                                <span>{message.token_count} tokens</span>
                              )}
                            </div>
                          )}

                          {/* Sources section */}
                          {!isUser && chunkReferences && chunkReferences.length > 0 && (
                            <div className="space-y-2 rounded-lg border bg-muted/30 p-3">
                              <p className="text-xs font-medium">Sources</p>
                              <div className="space-y-2">
                                {chunkReferences.map((chunk) => (
                                  <div
                                    key={chunk.chunk_id}
                                    className="rounded-md border bg-background/60 px-3 py-2 text-xs"
                                  >
                                    <div className="mb-1 flex flex-wrap items-center gap-2">
                                      <span className="font-medium">{chunk.video_title}</span>
                                      <span className="text-muted-foreground">
                                        {chunk.timestamp_display}
                                      </span>
                                      <span className="ml-auto text-[10px] text-muted-foreground">
                                        {(chunk.relevance_score * 100).toFixed(0)}% match
                                      </span>
                                    </div>
                                    <p className="line-clamp-2 text-[11px] text-muted-foreground">
                                      {chunk.text_snippet}
                                    </p>
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })}
                <div ref={messagesEndRef} />
              </div>
            )}
          </div>
        </div>

        {/* Input area - fixed at bottom like ChatGPT */}
        <div className="sticky bottom-0 border-t bg-background">
          <div className="mx-auto max-w-3xl px-4 py-4">
            <form onSubmit={handleSubmit}>
              <div className="flex gap-2">
                <Input
                  id="message"
                  placeholder="Message Mindful Learning..."
                  value={messageText}
                  onChange={(e) => setMessageText(e.target.value)}
                  disabled={sendMessageMutation.isPending}
                  className="flex-1 rounded-2xl"
                  autoComplete="off"
                />
                <Button
                  type="submit"
                  size="icon"
                  className="rounded-full"
                  disabled={sendMessageMutation.isPending || !messageText.trim()}
                >
                  {sendMessageMutation.isPending ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      viewBox="0 0 24 24"
                      fill="currentColor"
                      className="h-4 w-4"
                    >
                      <path d="M3.478 2.405a.75.75 0 00-.926.94l2.432 7.905H13.5a.75.75 0 010 1.5H4.984l-2.432 7.905a.75.75 0 00.926.94 60.519 60.519 0 0018.445-8.986.75.75 0 000-1.218A60.517 60.517 0 003.478 2.405z" />
                    </svg>
                  )}
                </Button>
              </div>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}
