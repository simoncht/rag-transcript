import { apiClient } from "./client";
import {
  Conversation,
  ConversationListResponse,
  ConversationWithMessages,
  MessageResponse,
  ConversationSourcesResponse,
} from "../types";

export const conversationsApi = {
  async list(skip = 0, limit = 50): Promise<ConversationListResponse> {
    const response = await apiClient.get("/conversations", {
      params: { skip, limit },
    });
    return response.data;
  },

  async get(conversationId: string): Promise<ConversationWithMessages> {
    const response = await apiClient.get(`/conversations/${conversationId}`);
    return response.data;
  },

  async create(
    title: string,
    options: { selectedVideoIds?: string[]; collectionId?: string }
  ): Promise<Conversation> {
    const response = await apiClient.post("/conversations", {
      title,
      selected_video_ids: options.selectedVideoIds,
      collection_id: options.collectionId,
    });
    return response.data;
  },

  async update(
    conversationId: string,
    title?: string,
    selectedVideoIds?: string[]
  ): Promise<Conversation> {
    const response = await apiClient.patch(`/conversations/${conversationId}`, {
      title,
      selected_video_ids: selectedVideoIds,
    });
    return response.data;
  },

  async delete(conversationId: string): Promise<void> {
    await apiClient.delete(`/conversations/${conversationId}`);
  },

  async sendMessage(
    conversationId: string,
    message: string,
    stream = false,
    model?: string,
    mode?: string
  ): Promise<MessageResponse> {
    const response = await apiClient.post(
      `/conversations/${conversationId}/messages`,
      {
        message,
        stream,
        model,
        mode,
      }
    );
    return response.data;
  },

  async getSources(conversationId: string): Promise<ConversationSourcesResponse> {
    const response = await apiClient.get(`/conversations/${conversationId}/sources`);
    return response.data;
  },

  async updateSources(
    conversationId: string,
    payload: { selected_video_ids?: string[]; add_video_ids?: string[] }
  ): Promise<ConversationSourcesResponse> {
    const response = await apiClient.patch(
      `/conversations/${conversationId}/sources`,
      payload
    );
    return response.data;
  },
};
