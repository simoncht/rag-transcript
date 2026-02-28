import { apiClient } from "./client";
import type {
  ContentItem,
  ContentListResponse,
  ContentUploadResponse,
  ContentDeleteResponse,
  ContentStatusUpdate,
} from "@/lib/types";

const CONTENT_LIST_TIMEOUT_MS = 15000;

export const contentApi = {
  async upload(
    file: File,
    title?: string
  ): Promise<ContentUploadResponse> {
    const formData = new FormData();
    formData.append("file", file);
    if (title) {
      formData.append("title", title);
    }

    const response = await apiClient.post("/content/upload", formData, {
      headers: {
        "Content-Type": "multipart/form-data",
      },
      timeout: 120000, // 2 min for large files
    });
    return response.data;
  },

  async list(
    skip = 0,
    limit = 50,
    contentType?: string,
    status?: string,
    search?: string
  ): Promise<ContentListResponse> {
    const params: Record<string, string | number> = { skip, limit };
    if (contentType) params.content_type = contentType;
    if (status) params.status = status;
    if (search) params.search = search;

    const response = await apiClient.get("/content", {
      params,
      timeout: CONTENT_LIST_TIMEOUT_MS,
    });
    return response.data;
  },

  async get(contentId: string): Promise<ContentItem> {
    const response = await apiClient.get(`/content/${contentId}`);
    return response.data;
  },

  async getStatus(contentId: string): Promise<ContentStatusUpdate> {
    const response = await apiClient.get(`/content/${contentId}/status`);
    return response.data;
  },

  async delete(contentId: string): Promise<ContentDeleteResponse> {
    const response = await apiClient.delete(`/content/${contentId}`);
    return response.data;
  },

  async deleteBulk(contentIds: string[]): Promise<ContentDeleteResponse> {
    const response = await apiClient.post("/content/delete-bulk", {
      content_ids: contentIds,
    });
    return response.data;
  },

  async reprocess(contentId: string): Promise<{ status: string; message: string }> {
    const response = await apiClient.post(`/content/${contentId}/reprocess`);
    return response.data;
  },

  async getCounts(): Promise<{ total: number; completed: number; processing: number; failed: number }> {
    const response = await apiClient.get("/content/counts");
    return response.data;
  },

  async cancel(contentId: string): Promise<{ content_id: string; message: string }> {
    const response = await apiClient.post(`/content/${contentId}/cancel`);
    return response.data;
  },

  async getLimits(): Promise<{
    tier: string;
    max_upload_size_mb: number;
    max_document_words: number;
  }> {
    const response = await apiClient.get("/content/limits");
    return response.data;
  },

  getFileUrl(contentId: string): string {
    return `/api/content/${contentId}/file`;
  },
};
