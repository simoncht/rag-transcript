export interface Video {
  id: string;
  youtube_url: string;
  youtube_id: string;
  title: string;
  thumbnail_url?: string;
  duration_seconds: number;
  status: "pending" | "processing" | "completed" | "failed";
  error_message?: string;
  tags: string[];
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

// Collection types
export interface Collection {
  id: string;
  name: string;
  description?: string;
  metadata: {
    instructor?: string;
    subject?: string;
    semester?: string;
    tags?: string[];
    [key: string]: any;
  };
  is_default: boolean;
  video_count: number;
  total_duration_seconds: number;
  created_at: string;
  updated_at: string;
}

export interface CollectionVideoInfo {
  id: string;
  title: string;
  youtube_id: string;
  duration_seconds?: number;
  status: string;
  thumbnail_url?: string;
  tags: string[];
  added_at: string;
  position?: number;
}

export interface CollectionDetail extends Collection {
  user_id: string;
  videos: CollectionVideoInfo[];
}

export interface CollectionListResponse {
  total: number;
  collections: Collection[];
}

export interface CollectionCreateRequest {
  name: string;
  description?: string;
  metadata?: {
    instructor?: string;
    subject?: string;
    semester?: string;
    tags?: string[];
    [key: string]: any;
  };
}

export interface CollectionUpdateRequest {
  name?: string;
  description?: string;
  metadata?: {
    instructor?: string;
    subject?: string;
    semester?: string;
    tags?: string[];
    [key: string]: any;
  };
}

export interface CollectionAddVideosRequest {
  video_ids: string[];
}

export interface VideoUpdateTagsRequest {
  tags: string[];
}
