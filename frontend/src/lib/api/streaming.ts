import { getCachedToken } from "./client";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "";
const API_V1_PREFIX = process.env.NEXT_PUBLIC_API_V1_PREFIX || "/api/v1";

export interface StreamDoneData {
  messageId: string;
  sources: any[];
  tokenCount: number;
  responseTime: number;
  confidence?: {
    level: "strong" | "moderate" | "limited";
    avg_relevance: number;
    chunk_count: number;
    unique_videos: number;
  };
  retrievalMetadata?: {
    original_query?: string;
    effective_query?: string | null;
    retrieval_type?: string;
    total_retrieved?: number;
    total_after_filter?: number;
    total_after_rerank?: number;
    final_chunks?: number;
    unique_videos?: number;
    timing?: { retrieval_ms?: number; rewrite_ms?: number; llm_ms?: number; total_ms?: number };
  };
  pipelineTiming?: { rewrite_ms?: number; retrieval_ms?: number; llm_ms?: number };
  reasoningContent?: string;
  reasoningTokens?: number;
  newFactsCount?: number;
}

export interface StreamStatusData {
  stage: "analyzing" | "searching" | "generating";
  message: string;
}

export interface StreamMessageParams {
  conversationId: string;
  message: string;
  model?: string;
  mode?: string;
  signal?: AbortSignal;
  onContent: (chunk: string) => void;
  onDone: (data: StreamDoneData) => void;
  onStatus?: (data: StreamStatusData) => void;
  onFollowUpQuestions?: (questions: string[]) => void;
  onError: (error: string) => void;
}

/**
 * Stream a message response from the backend using Server-Sent Events (SSE).
 * Uses fetch API instead of EventSource because the backend endpoint uses POST.
 *
 * Event format from backend:
 * - data: {"type": "content", "content": "chunk text"}
 * - data: {"type": "done", "message_id": "...", "sources": [...], "token_count": N, "response_time_seconds": N.N}
 * - data: {"type": "error", "error": "message"}
 */
export async function streamMessage({
  conversationId,
  message,
  model,
  mode = "summarize",
  signal,
  onContent,
  onDone,
  onStatus,
  onFollowUpQuestions,
  onError,
}: StreamMessageParams): Promise<void> {
  const token = await getCachedToken();
  const url = `${API_BASE_URL}${API_V1_PREFIX}/conversations/${conversationId}/messages/stream`;

  let response: Response;
  try {
    response = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({ message, model, mode, stream: true }),
      signal,
    });
  } catch (error: any) {
    if (error.name === "AbortError") {
      return; // User cancelled, not an error
    }
    onError(error.message || "Failed to connect to server");
    return;
  }

  if (!response.ok) {
    const errorText = await response.text().catch(() => "");
    let errorMessage = `Request failed with status ${response.status}`;
    try {
      const errorJson = JSON.parse(errorText);
      const detail = errorJson.detail;

      // Handle quota exceeded error (detail is an object with quota info)
      if (detail && typeof detail === "object" && detail.error === "quota_exceeded") {
        errorMessage = detail.message || "Quota exceeded. Upgrade your plan to continue.";
      } else if (typeof detail === "string") {
        errorMessage = detail;
      } else if (errorJson.message) {
        errorMessage = errorJson.message;
      }
    } catch {
      if (errorText) {
        errorMessage = errorText;
      }
    }
    onError(errorMessage);
    return;
  }

  const reader = response.body?.getReader();
  if (!reader) {
    onError("No response body");
    return;
  }

  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      // SSE events are separated by double newlines
      const lines = buffer.split("\n\n");
      // Keep the incomplete last line in the buffer
      buffer = lines.pop() || "";

      for (const line of lines) {
        if (line.startsWith("data: ")) {
          try {
            const eventData = JSON.parse(line.slice(6));

            if (eventData.type === "status") {
              onStatus?.({
                stage: eventData.stage,
                message: eventData.message,
              });
            } else if (eventData.type === "content") {
              onContent(eventData.content);
            } else if (eventData.type === "done") {
              onDone({
                messageId: eventData.message_id,
                sources: eventData.sources || [],
                tokenCount: eventData.token_count || 0,
                responseTime: eventData.response_time_seconds || 0,
                confidence: eventData.confidence,
                retrievalMetadata: eventData.retrieval_metadata,
                reasoningContent: eventData.reasoning_content,
                reasoningTokens: eventData.reasoning_tokens,
                newFactsCount: eventData.new_facts_count,
              });
            } else if (eventData.type === "followup_questions") {
              onFollowUpQuestions?.(eventData.questions || []);
            } else if (eventData.type === "error") {
              onError(eventData.error || "Unknown streaming error");
            }
          } catch {
            // Skip malformed JSON events
          }
        }
      }
    }

    // Process any remaining data in buffer
    if (buffer.startsWith("data: ")) {
      try {
        const eventData = JSON.parse(buffer.slice(6));
        if (eventData.type === "content") {
          onContent(eventData.content);
        } else if (eventData.type === "done") {
          onDone({
            messageId: eventData.message_id,
            sources: eventData.sources || [],
            tokenCount: eventData.token_count || 0,
            responseTime: eventData.response_time_seconds || 0,
          });
        } else if (eventData.type === "error") {
          onError(eventData.error || "Unknown streaming error");
        }
      } catch {
        // Skip malformed JSON
      }
    }
  } catch (error: any) {
    if (error.name === "AbortError") {
      return; // User cancelled
    }
    onError(error.message || "Stream error");
  } finally {
    reader.releaseLock();
  }
}
