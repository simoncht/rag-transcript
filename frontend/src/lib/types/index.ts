export interface Video {
  id: string;
  youtube_url: string;
  youtube_id: string;
  title: string;
  thumbnail_url?: string;
  duration_seconds: number;
  status:
    | "pending"
    | "processing"
    | "downloading"
    | "transcribing"
    | "chunking"
    | "enriching"
    | "indexing"
    | "completed"
    | "failed";
  progress_percent?: number;
  error_message?: string;
  tags: string[];
  audio_file_size_mb?: number;
  transcript_size_mb?: number;
  storage_total_mb?: number;
  created_at: string;
  updated_at: string;
}

export interface TranscriptSegment {
  text: string;
  start: number;
  end: number;
  speaker?: string;
}

export interface TranscriptDetail {
  video_id: string;
  full_text: string;
  language?: string;
  duration_seconds: number;
  word_count: number;
  has_speaker_labels: boolean;
  speaker_count?: number;
  created_at: string;
  segments: TranscriptSegment[];
}

export interface VideoDeleteBreakdown {
  video_id: string;
  title: string;
  audio_size_mb: number;
  transcript_size_mb: number;
  index_size_mb: number;
  total_size_mb: number;
}

export interface VideoDeleteRequest {
  video_ids: string[];
  remove_from_library: boolean;
  delete_search_index: boolean;
  delete_audio: boolean;
  delete_transcript: boolean;
}

export interface VideoDeleteResponse {
  deleted_count: number;
  videos: VideoDeleteBreakdown[];
  total_savings_mb: number;
  message: string;
}

export interface Conversation {
  id: string;
  title: string;
  collection_id?: string | null;
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
  chunk_references?: ChunkReference[];
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
  rank: number;
}

export interface MessageResponse {
  message_id: string;
  conversation_id: string;
  role: "assistant";
  content: string;
  chunk_references: ChunkReference[];
  token_count: number;
  response_time_seconds: number;
  model?: string;
}

export interface ConversationWithMessages extends Conversation {
  messages: Message[];
}

export interface ConversationSource {
  conversation_id: string;
  video_id: string;
  is_selected: boolean;
  added_at: string;
  added_via?: string;
  title?: string;
  status?: string;
  duration_seconds?: number;
  thumbnail_url?: string;
  youtube_id?: string;
}

export interface ConversationSourcesResponse {
  total: number;
  selected: number;
  sources: ConversationSource[];
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

export interface QuotaStat {
  used: number;
  limit: number;
  remaining: number;
  percentage: number;
}

export interface StorageBreakdown {
  total_mb: number;
  limit_mb: number;
  remaining_mb: number;
  percentage: number;
  audio_mb: number;
  transcript_mb: number;
  disk_usage_mb: number;
}

export interface UsageCounts {
  videos_total: number;
  videos_completed: number;
  videos_processing: number;
  videos_failed: number;
  transcripts: number;
  chunks: number;
}

export interface VectorStoreStat {
  collection_name: string;
  total_points: number;
  vectors_count: number;
  indexed_vectors_count: number;
}

export interface UsageSummary {
  period_start: string;
  period_end: string;
  videos: QuotaStat;
  minutes: QuotaStat;
  messages: QuotaStat;
  storage_mb: QuotaStat;
  storage_breakdown: StorageBreakdown;
  counts: UsageCounts;
  vector_store?: VectorStoreStat;
}
