export interface Video {
  id: string;
  youtube_url: string;
  title: string;
  duration_seconds: number;
  status: "pending" | "processing" | "completed" | "failed";
  error_message?: string;
  created_at: string;
  updated_at: string;
}

export interface Conversation {
  id: string;
  title: string;
  selected_video_ids: string[];
  message_count: number;
  total_tokens_used: number;
  created_at: string;
  updated_at: string;
  last_message_at?: string;
}

export interface Message {
  id: string;
  conversation_id: string;
  role: "user" | "assistant";
  content: string;
  token_count: number;
  chunks_retrieved_count?: number;
  response_time_seconds?: number;
  created_at: string;
}

export interface ChunkReference {
  chunk_id: string;
  video_id: string;
  video_title: string;
  start_timestamp: number;
  end_timestamp: number;
  text_snippet: string;
  relevance_score: number;
  timestamp_display: string;
}

export interface MessageResponse {
  message_id: string;
  conversation_id: string;
  role: "assistant";
  content: string;
  chunk_references: ChunkReference[];
  token_count: number;
  response_time_seconds: number;
}

export interface ConversationWithMessages extends Conversation {
  messages: Message[];
}

export interface VideoListResponse {
  total: number;
  videos: Video[];
}

export interface ConversationListResponse {
  total: number;
  conversations: Conversation[];
}
