import { apiClient } from "./client";
import type { ConversationInsightsResponse, TopicChunksResponse } from "../types";

export const insightsApi = {
  async getInsights(
    conversationId: string,
    regenerate = false
  ): Promise<ConversationInsightsResponse> {
    const response = await apiClient.get(`/conversations/${conversationId}/insights`, {
      params: { regenerate },
    });
    return response.data;
  },

  async getTopicChunks(
    conversationId: string,
    topicId: string
  ): Promise<TopicChunksResponse> {
    const encoded = encodeURIComponent(topicId);
    const response = await apiClient.get(
      `/conversations/${conversationId}/insights/topics/${encoded}/chunks`
    );
    return response.data;
  },
};

