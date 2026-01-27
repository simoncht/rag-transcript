import { apiClient } from "./client";
import type {
  DashboardResponse,
  UserListResponse,
  UserDetail,
  UserUpdateRequest,
  QuotaOverrideRequest,
  QAFeedResponse,
  AdminConversationListResponse,
  AdminConversationDetail,
  ContentOverviewResponse,
  AbuseAlertResponse,
  AuditLogResponse,
  LLMUsageResponse,
} from "../types";

export const adminApi = {
  /**
   * Get admin dashboard statistics
   */
  async getDashboard(): Promise<DashboardResponse> {
    const response = await apiClient.get("/admin/dashboard");
    return response.data;
  },

  /**
   * List all users with pagination, search, and filters
   */
  async listUsers(params?: {
    page?: number;
    page_size?: number;
    search?: string;
    tier?: string;
    status?: string;
  }): Promise<UserListResponse> {
    const response = await apiClient.get("/admin/users", { params });
    return response.data;
  },

  /**
   * Get detailed user information including metrics and costs
   */
  async getUserDetail(userId: string): Promise<UserDetail> {
    const response = await apiClient.get(`/admin/users/${userId}`);
    return response.data;
  },

  /**
   * Update user settings
   */
  async updateUser(
    userId: string,
    data: UserUpdateRequest
  ): Promise<UserDetail> {
    const response = await apiClient.patch(`/admin/users/${userId}`, data);
    return response.data;
  },

  /**
   * Override user quota limits
   */
  async overrideQuota(
    userId: string,
    data: QuotaOverrideRequest
  ): Promise<{ message: string }> {
    const response = await apiClient.patch(
      `/admin/users/${userId}/quota`,
      data
    );
    return response.data;
  },

  /**
   * Fetch paginated question/answer feed for monitoring
   */
  async getQAFeed(params?: {
    page?: number;
    page_size?: number;
    user_id?: string;
    conversation_id?: string;
    collection_id?: string;
    search?: string;
    start?: string;
    end?: string;
  }): Promise<QAFeedResponse> {
    const response = await apiClient.get("/admin/qa-feed", { params });
    return response.data;
  },

  /**
   * Fetch admin audit log entries (chat monitoring)
   */
  async getAuditLogs(params?: {
    page?: number;
    page_size?: number;
    event_type?: string;
    user_id?: string;
    conversation_id?: string;
    role?: string;
    has_flags?: boolean;
    search?: string;
    start?: string;
    end?: string;
  }): Promise<AuditLogResponse> {
    const response = await apiClient.get("/admin/audit/messages", { params });
    return response.data;
  },

  /**
   * List conversations for admin oversight
   */
  async listConversations(params?: {
    page?: number;
    page_size?: number;
    user_id?: string;
    collection_id?: string;
    search?: string;
  }): Promise<AdminConversationListResponse> {
    const response = await apiClient.get("/admin/conversations", { params });
    return response.data;
  },

  /**
   * Get combined content overview (videos + collections)
   */
  async getContentOverview(): Promise<ContentOverviewResponse> {
    const response = await apiClient.get("/admin/content/overview");
    return response.data;
  },

  /**
   * Get admin alerts (placeholder)
   */
  async getAlerts(): Promise<AbuseAlertResponse> {
    const response = await apiClient.get("/admin/alerts");
    return response.data;
  },

  /**
   * Get LLM usage statistics and cost tracking
   */
  async getLLMUsage(params?: {
    days?: number;
    limit?: number;
  }): Promise<LLMUsageResponse> {
    const response = await apiClient.get("/admin/llm-usage", { params });
    return response.data;
  },
};
