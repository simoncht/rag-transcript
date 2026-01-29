import { useState, useRef, useCallback, useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { streamMessage, StreamDoneData } from "@/lib/api/streaming";
import type { ChunkReference, ConversationWithMessages, Message } from "@/lib/types";

interface StreamingState {
  isStreaming: boolean;
  content: string;
  sources: ChunkReference[];
  error: string | null;
  messageId: string | null;
  startTime: number | null;
}

const initialState: StreamingState = {
  isStreaming: false,
  content: "",
  sources: [],
  error: null,
  messageId: null,
  startTime: null,
};

/**
 * React hook for managing streaming chat messages with React Query cache integration.
 *
 * Features:
 * - Optimistic user message addition
 * - Progressive content streaming
 * - Automatic cache updates on completion
 * - Cancellation support via AbortController
 * - Elapsed time tracking
 */
export function useStreamingMessage(conversationId: string) {
  const queryClient = useQueryClient();
  const abortRef = useRef<AbortController | null>(null);
  // Track content in ref so it's available in onDone callback without stale closure
  const contentRef = useRef("");

  const [state, setState] = useState<StreamingState>(initialState);

  // Cleanup abort controller on unmount
  useEffect(() => {
    return () => {
      abortRef.current?.abort();
    };
  }, []);

  const sendMessage = useCallback(
    async (message: string, model?: string, mode?: string) => {
      // Abort any existing stream
      abortRef.current?.abort();
      abortRef.current = new AbortController();
      contentRef.current = "";

      setState({
        isStreaming: true,
        content: "",
        sources: [],
        error: null,
        messageId: null,
        startTime: Date.now(),
      });

      // Optimistically add user message to cache
      const userMsgId = crypto.randomUUID();
      queryClient.setQueryData<ConversationWithMessages>(
        ["conversation", conversationId],
        (prev) => {
          if (!prev) return prev;
          return {
            ...prev,
            messages: [
              ...prev.messages,
              {
                id: userMsgId,
                conversation_id: conversationId,
                role: "user" as const,
                content: message,
                token_count: message.split(/\s+/).length, // rough estimate
                created_at: new Date().toISOString(),
              },
            ],
          };
        }
      );

      try {
        await streamMessage({
          conversationId,
          message,
          model,
          mode,
          signal: abortRef.current.signal,
          onContent: (chunk: string) => {
            contentRef.current += chunk;
            setState((s) => ({
              ...s,
              content: s.content + chunk,
            }));
          },
          onDone: (data: StreamDoneData) => {
            const { messageId, sources, tokenCount, responseTime } = data;
            setState((s) => ({
              ...s,
              isStreaming: false,
              messageId,
              sources: sources as ChunkReference[],
            }));

            // Add assistant message to cache
            queryClient.setQueryData<ConversationWithMessages>(
              ["conversation", conversationId],
              (prev) => {
                if (!prev) return prev;
                const newMessage: Message & { chunk_references?: ChunkReference[] } = {
                  id: messageId,
                  conversation_id: conversationId,
                  role: "assistant" as const,
                  content: contentRef.current,
                  token_count: tokenCount,
                  chunks_retrieved_count: sources.length,
                  response_time_seconds: responseTime,
                  created_at: new Date().toISOString(),
                  chunk_references: sources as ChunkReference[],
                };
                return {
                  ...prev,
                  messages: [...prev.messages, newMessage],
                };
              }
            );

            // Invalidate quota cache to reflect the new message count
            queryClient.invalidateQueries({ queryKey: ["subscription-quota"] });
          },
          onError: (error: string) => {
            setState((s) => ({
              ...s,
              isStreaming: false,
              error,
            }));
          },
        });
      } catch (e: any) {
        if (e.name !== "AbortError") {
          setState((s) => ({
            ...s,
            isStreaming: false,
            error: e.message || "Streaming error",
          }));
        }
      }
    },
    [conversationId, queryClient]
  );

  const cancelStream = useCallback(() => {
    abortRef.current?.abort();
    setState((s) => ({
      ...s,
      isStreaming: false,
    }));
  }, []);

  // Calculate elapsed time for display
  const elapsedTime = state.startTime ? (Date.now() - state.startTime) / 1000 : null;

  return {
    isStreaming: state.isStreaming,
    content: state.content,
    sources: state.sources,
    error: state.error,
    messageId: state.messageId,
    elapsedTime,
    sendMessage,
    cancelStream,
  };
}
