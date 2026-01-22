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
    | "failed"
    | "canceled";
  progress_percent?: number;
  error_message?: string;
  tags: string[];
  audio_file_size_mb?: number;
  transcript_size_mb?: number;
  storage_total_mb?: number;
  created_at: string;
  updated_at: string;
}

// Cancel types
export type CleanupOption = "keep_video" | "full_delete";

export interface VideoCancelRequest {
  cleanup_option: CleanupOption;
}

export interface CleanupSummary {
  transcript_deleted: boolean;
  chunks_deleted: number;
  audio_file_deleted: boolean;
  transcript_file_deleted: boolean;
  vectors_deleted: boolean;
}

export interface VideoCancelResponse {
  video_id: string;
  previous_status: string;
  new_status: string;
  celery_task_revoked: boolean;
  cleanup_summary: CleanupSummary;
}

export interface BulkCancelRequest {
  video_ids: string[];
  cleanup_option: CleanupOption;
}

export interface BulkCancelResultItem {
  video_id: string;
  success: boolean;
  previous_status?: string;
  new_status?: string;
  error?: string;
}

export interface BulkCancelResponse {
  total: number;
  canceled: number;
  skipped: number;
  results: BulkCancelResultItem[];
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
  role: "user" | "assistant" | "system";
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
  youtube_id?: string | null;
  video_url?: string | null;
  jump_url?: string | null;
  transcript_url?: string | null;
  start_timestamp: number;
  end_timestamp: number;
  text_snippet: string;
  relevance_score: number;
  timestamp_display: string;
  rank: number;
  // Phase 1 enhancement: contextual metadata
  speakers?: string[] | null;
  chapter_title?: string | null;
  channel_name?: string | null;
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
  is_deleted?: boolean;
  selectable?: boolean;
  selectable_reason?: string;
  duration_seconds?: number;
  thumbnail_url?: string;
  youtube_id?: string;
}

export interface ConversationSourcesResponse {
  total: number;
  selected: number;
  sources: ConversationSource[];
}

export interface EmbeddingPreset {
  key: string;
  model: string;
  dimensions: number;
}

export interface EmbeddingSettingsResponse {
  active_key: string;
  active_model: string;
  dimensions: number;
  collection_name: string;
  presets: EmbeddingPreset[];
  reembed_task_id?: string;
  message?: string;
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

export interface ReactFlowPosition {
  x: number;
  y: number;
}

export interface InsightNode<TData = Record<string, any>> {
  id: string;
  type: string;
  position: ReactFlowPosition;
  data: TData;
}

export interface InsightEdge {
  id: string;
  source: string;
  target: string;
  type?: string;
}

export interface InsightGraph {
  nodes: InsightNode[];
  edges: InsightEdge[];
}

export interface ConversationInsightsMetadata {
  topics_count: number;
  total_chunks_analyzed: number;
  generation_time_seconds?: number | null;
  cached: boolean;
  created_at: string;
  llm_provider?: string | null;
  llm_model?: string | null;
  extraction_prompt_version: number;
}

export interface ConversationInsightsResponse {
  conversation_id: string;
  graph: InsightGraph;
  metadata: ConversationInsightsMetadata;
}

export interface TopicInsightChunk {
  chunk_id: string;
  video_id: string;
  video_title: string;
  start_timestamp: number;
  end_timestamp: number;
  timestamp_display: string;
  text: string;
  chunk_title?: string | null;
  chapter_title?: string | null;
  chunk_summary?: string | null;
}

export interface TopicChunksResponse {
  topic_id: string;
  topic_label: string;
  chunks: TopicInsightChunk[];
}

// Admin types
export interface SystemStats {
  total_users: number;
  users_by_tier: Record<string, number>;
  active_users: number;
  inactive_users: number;
  new_users_this_month: number;
  total_videos: number;
  videos_completed: number;
  videos_processing: number;
  videos_failed: number;
  total_conversations: number;
  total_messages: number;
  total_transcription_minutes: number;
  total_tokens_used: number;
  total_storage_gb: number;
}

export interface UserEngagementStats {
  active_users: number;
  at_risk_users: number;
  churning_users: number;
  dormant_users: number;
}

export interface DashboardResponse {
  system_stats: SystemStats;
  engagement_stats: UserEngagementStats;
}

export interface UserSummary {
  id: string;
  email: string;
  full_name?: string;
  oauth_provider?: string;
  oauth_provider_id?: string;
  subscription_tier: string;
  subscription_status: string;
  is_active: boolean;
  is_superuser: boolean;
  created_at: string;
  last_active_at?: string;
  video_count: number;
  collection_count: number;
  conversation_count: number;
  total_messages: number;
  total_tokens_used: number;
  storage_mb_used: number;
  days_since_signup: number;
  days_since_last_active?: number;
}

export interface UserListResponse {
  total: number;
  page: number;
  page_size: number;
  users: UserSummary[];
}

export interface UserDetailMetrics {
  videos_total: number;
  videos_completed: number;
  videos_processing: number;
  videos_failed: number;
  total_transcription_minutes: number;
  collections_total: number;
  collections_with_videos: number;
  conversations_total: number;
  conversations_active: number;
  messages_sent: number;
  messages_received: number;
  total_tokens: number;
  input_tokens: number;
  output_tokens: number;
  storage_mb: number;
  audio_mb: number;
  transcript_mb: number;
  quota_videos_used: number;
  quota_videos_limit: number;
  quota_minutes_used: number;
  quota_minutes_limit: number;
  quota_messages_used: number;
  quota_messages_limit: number;
  quota_storage_used: number;
  quota_storage_limit: number;
}

export interface UserCostBreakdown {
  transcription_cost: number;
  embedding_cost: number;
  llm_cost: number;
  storage_cost: number;
  total_cost: number;
  subscription_revenue: number;
  net_profit: number;
  profit_margin: number;
}

export interface UserDetail {
  id: string;
  email: string;
  full_name?: string;
  oauth_provider?: string;
  oauth_provider_id?: string;
  subscription_tier: string;
  subscription_status: string;
  is_active: boolean;
  is_superuser: boolean;
  created_at: string;
  updated_at: string;
  last_login_at?: string;
  metrics: UserDetailMetrics;
  costs: UserCostBreakdown;
}

export interface UserUpdateRequest {
  subscription_tier?: string;
  subscription_status?: string;
  is_active?: boolean;
  is_superuser?: boolean;
}

export interface QuotaOverrideRequest {
  videos_limit?: number;
  minutes_limit?: number;
  messages_limit?: number;
  storage_mb_limit?: number;
}

export interface QASource {
  chunk_id: string;
  video_id: string;
  video_title?: string;
  score?: number;
  snippet?: string;
  start_timestamp?: number;
  end_timestamp?: number;
}

export interface QAFeedItem {
  qa_id: string;
  question_id: string;
  answer_id?: string;
  user_id: string;
  user_email?: string;
  conversation_id: string;
  collection_id?: string;
  question: string;
  answer?: string;
  asked_at: string;
  answered_at?: string;
  response_latency_ms?: number;
  input_tokens?: number;
  output_tokens?: number;
  cost_usd?: number;
  flags: string[];
  sources: QASource[];
}

export interface QAFeedResponse {
  total: number;
  page: number;
  page_size: number;
  items: QAFeedItem[];
}

export interface AuditLogItem {
  id: string;
  event_type: string;
  user_id?: string | null;
  user_email?: string | null;
  conversation_id?: string | null;
  message_id?: string | null;
  role?: string | null;
  content?: string | null;
  token_count?: number | null;
  input_tokens?: number | null;
  output_tokens?: number | null;
  flags: string[];
  created_at: string;
  ip_hash?: string | null;
  user_agent?: string | null;
  metadata?: Record<string, any>;
}

export interface AuditLogResponse {
  total: number;
  page: number;
  page_size: number;
  items: AuditLogItem[];
}

export interface AdminConversationSummary {
  id: string;
  user_id: string;
  user_email?: string;
  title?: string;
  collection_id?: string;
  message_count: number;
  total_tokens: number;
  started_at: string;
  last_message_at?: string;
}

export interface AdminConversationListResponse {
  total: number;
  page: number;
  page_size: number;
  conversations: AdminConversationSummary[];
}

export interface AdminConversationMessage {
  id: string;
  role: string;
  content: string;
  created_at: string;
  input_tokens?: number;
  output_tokens?: number;
  response_time_seconds?: number;
  sources: QASource[];
}

export interface AdminConversationDetail {
  id: string;
  user_id: string;
  user_email?: string;
  title?: string;
  collection_id?: string;
  message_count: number;
  total_tokens: number;
  created_at: string;
  updated_at: string;
  last_message_at?: string;
  messages: AdminConversationMessage[];
}

export interface AdminVideoItem {
  id: string;
  title: string;
  user_email?: string;
  status: string;
  progress_percent: number;
  error_message?: string;
  created_at: string;
  updated_at: string;
}

export interface AdminVideoOverview {
  total: number;
  completed: number;
  processing: number;
  failed: number;
  queued: number;
  recent: AdminVideoItem[];
}

export interface AdminCollectionOverview {
  total: number;
  with_videos: number;
  empty: number;
  recent_created: string[];
}

export interface ContentOverviewResponse {
  videos: AdminVideoOverview;
  collections: AdminCollectionOverview;
}

export interface AbuseAlert {
  user_id: string;
  user_email: string;
  alert_type: string;
  severity: string;
  description: string;
  detected_at: string;
  is_resolved: boolean;
}

export interface AbuseAlertResponse {
  total: number;
  alerts: AbuseAlert[];
}

// Subscription types
export type SubscriptionTier = "free" | "pro" | "enterprise";
export type SubscriptionStatus = "active" | "canceled" | "past_due" | "trialing" | "incomplete";

export interface SubscriptionDetail {
  id: string;
  user_id: string;
  tier: SubscriptionTier;
  status: SubscriptionStatus;
  stripe_subscription_id?: string | null;
  stripe_customer_id: string;
  stripe_price_id: string;
  current_period_start?: string | null;
  current_period_end?: string | null;
  cancel_at_period_end: boolean;
  canceled_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface QuotaUsage {
  tier: SubscriptionTier;
  videos_used: number;
  videos_limit: number;
  videos_remaining: number;
  messages_used: number;
  messages_limit: number;
  messages_remaining: number;
  storage_used_mb: number;
  storage_limit_mb: number;
  storage_remaining_mb: number;
  minutes_used: number;
  minutes_limit: number;
  minutes_remaining: number;
}

export interface PricingTier {
  tier: SubscriptionTier;
  name: string;
  price_monthly: number; // in cents
  price_yearly: number; // in cents
  stripe_price_id_monthly?: string | null;
  stripe_price_id_yearly?: string | null;
  features: string[];
  video_limit: number;
  message_limit: number;
  storage_limit_mb: number;
  minutes_limit: number;
}

export interface CheckoutSessionRequest {
  tier: SubscriptionTier;
  success_url: string;
  cancel_url: string;
}

export interface CheckoutSessionResponse {
  checkout_url: string;
  session_id: string;
}

export interface CustomerPortalRequest {
  return_url: string;
}

export interface CustomerPortalResponse {
  portal_url: string;
}
