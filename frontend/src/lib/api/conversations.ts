import { apiClient } from "./client";
import {
  Conversation,
  ConversationListResponse,
  ConversationWithMessages,
  MessageResponse,
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
    selectedVideoIds: string[]
  ): Promise<Conversation> {
    const response = await apiClient.post("/conversations", {
      title,
      selected_video_ids: selectedVideoIds,
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
    stream = false
  ): Promise<MessageResponse> {
    const response = await apiClient.post(
      `/conversations/${conversationId}/messages`,
      {
        message,
        stream,
      }
    );
    return response.data;
  },
};
