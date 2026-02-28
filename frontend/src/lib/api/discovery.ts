import { apiClient } from "./client";
import {
  YouTubeSearchRequest,
  YouTubeSearchResponse,
  YouTubeDurationFilter,
  YouTubePublishedFilter,
  YouTubeOrderFilter,
  YouTubeCategoryFilter,
  BatchImportRequest,
  BatchImportResponse,
  DiscoverySource,
  DiscoverySourceCreateRequest,
  DiscoverySourceUpdateRequest,
  DiscoverySourceListResponse,
  DiscoveredContent,
  DiscoveredContentListResponse,
  DiscoveredContentAction,
  ChannelInfo,
  RecommendationsResponse,
} from "../types";

export const discoveryApi = {
  // ==========================================
  // YouTube Search
  // ==========================================

  async search(
    query: string,
    maxResults = 25,
    pageToken?: string,
    filters?: {
      duration?: YouTubeDurationFilter;
      published_after?: YouTubePublishedFilter;
      order?: YouTubeOrderFilter;
      category?: YouTubeCategoryFilter;
    }
  ): Promise<YouTubeSearchResponse> {
    const request: YouTubeSearchRequest = {
      query,
      max_results: maxResults,
    };
    if (pageToken) {
      request.page_token = pageToken;
    }
    // Apply filters
    if (filters) {
      if (filters.duration) {
        request.duration = filters.duration;
      }
      if (filters.published_after) {
        request.published_after = filters.published_after;
      }
      if (filters.order) {
        request.order = filters.order;
      }
      if (filters.category) {
        request.category = filters.category;
      }
    }
    const response = await apiClient.post("/discovery/search", request);
    return response.data;
  },

  async batchImport(
    videoIds: string[],
    collectionId?: string
  ): Promise<BatchImportResponse> {
    const request: BatchImportRequest = {
      video_ids: videoIds,
      collection_id: collectionId,
    };
    const response = await apiClient.post("/discovery/import", request);
    return response.data;
  },

  // ==========================================
  // Discovery Sources (Subscriptions)
  // ==========================================

  async listSources(
    skip = 0,
    limit = 50,
    sourceType?: string,
    isActive?: boolean
  ): Promise<DiscoverySourceListResponse> {
    const params: Record<string, string | number | boolean> = { skip, limit };
    if (sourceType) params.source_type = sourceType;
    if (isActive !== undefined) params.is_active = isActive;

    const response = await apiClient.get("/discovery/sources", { params });
    return response.data;
  },

  async getSource(sourceId: string): Promise<DiscoverySource> {
    const response = await apiClient.get(`/discovery/sources/${sourceId}`);
    return response.data;
  },

  async createSource(
    request: DiscoverySourceCreateRequest
  ): Promise<DiscoverySource> {
    const response = await apiClient.post("/discovery/sources", request);
    return response.data;
  },

  async updateSource(
    sourceId: string,
    request: DiscoverySourceUpdateRequest
  ): Promise<DiscoverySource> {
    const response = await apiClient.patch(
      `/discovery/sources/${sourceId}`,
      request
    );
    return response.data;
  },

  async deleteSource(sourceId: string): Promise<void> {
    await apiClient.delete(`/discovery/sources/${sourceId}`);
  },

  async getChannelInfo(channelIdentifier: string): Promise<ChannelInfo> {
    const response = await apiClient.post("/discovery/channel-info", {
      channel_url: channelIdentifier,
    });
    return response.data;
  },

  // ==========================================
  // Discovered Content
  // ==========================================

  async listDiscoveredContent(
    skip = 0,
    limit = 50,
    status?: string,
    sourceType?: string
  ): Promise<DiscoveredContentListResponse> {
    const params: Record<string, string | number> = { skip, limit };
    if (status) params.status = status;
    if (sourceType) params.source_type = sourceType;

    const response = await apiClient.get("/discovery/content", { params });
    return response.data;
  },

  async actionContent(
    contentId: string,
    action: DiscoveredContentAction,
    collectionId?: string
  ): Promise<DiscoveredContent> {
    const response = await apiClient.post(`/discovery/content/${contentId}/action`, {
      action,
      collection_id: collectionId,
    });
    return response.data;
  },

  async actionBulk(
    contentIds: string[],
    action: DiscoveredContentAction,
    collectionId?: string
  ): Promise<{ actioned: number; results: Array<{ id: string; success: boolean; error?: string }> }> {
    const response = await apiClient.post("/discovery/content/bulk-action", {
      content_ids: contentIds,
      action,
      collection_id: collectionId,
    });
    return response.data;
  },

  // ==========================================
  // Recommendations
  // ==========================================

  async getRecommendations(
    strategies?: string[],
    limit = 10
  ): Promise<RecommendationsResponse> {
    const params: Record<string, string | number> = { limit };
    if (strategies && strategies.length > 0) {
      params.strategies = strategies.join(",");
    }

    const response = await apiClient.get("/discovery/recommendations", { params });
    return response.data;
  },
};
