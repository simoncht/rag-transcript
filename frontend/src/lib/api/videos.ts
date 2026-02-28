import { apiClient } from "./client";
import {
  Video,
  VideoListResponse,
  VideoFilterValues,
  VideoUpdateTagsRequest,
  TranscriptDetail,
  VideoDeleteRequest,
  VideoDeleteResponse,
  VideoCancelRequest,
  VideoCancelResponse,
  BulkCancelRequest,
  BulkCancelResponse,
  CleanupOption,
  SimilarVideosResponse,
} from "../types";

const VIDEO_LIST_TIMEOUT_MS = 15000;

export interface VideoListParams {
  skip?: number;
  limit?: number;
  status?: string;
  q?: string;
  sort?: string;
  channel?: string;
  tags?: string;
  duration_min?: number;
  duration_max?: number;
}

export const videosApi = {
  async list(
    skip = 0,
    limit = 50,
    status?: string,
    q?: string,
    sort?: string,
    channel?: string,
    tags?: string,
    durationMin?: number,
    durationMax?: number,
  ): Promise<VideoListResponse> {
    const params: Record<string, string | number> = { skip, limit };
    if (status) params.status = status;
    if (q) params.q = q;
    if (sort) params.sort = sort;
    if (channel) params.channel = channel;
    if (tags) params.tags = tags;
    if (durationMin !== undefined) params.duration_min = durationMin;
    if (durationMax !== undefined) params.duration_max = durationMax;
    const response = await apiClient.get("/videos", {
      params,
      timeout: VIDEO_LIST_TIMEOUT_MS,
      timeoutErrorMessage: "Video list request timed out. Ensure the backend is reachable.",
    });
    return response.data;
  },

  async getFilters(): Promise<VideoFilterValues> {
    const response = await apiClient.get("/videos/filters");
    return response.data;
  },

  async get(videoId: string): Promise<Video> {
    const response = await apiClient.get(`/videos/${videoId}`);
    return response.data;
  },

  async ingest(youtubeUrl: string): Promise<Video> {
    const response = await apiClient.post("/videos/ingest", {
      youtube_url: youtubeUrl,
    });
    return response.data;
  },

  async delete(videoId: string): Promise<void> {
    await apiClient.delete(`/videos/${videoId}`);
  },

  async deleteMultiple(request: VideoDeleteRequest): Promise<VideoDeleteResponse> {
    const response = await apiClient.post("/videos/delete", request);
    return response.data;
  },

  async updateTags(videoId: string, tags: string[]): Promise<Video> {
    const response = await apiClient.patch(`/videos/${videoId}/tags`, {
      tags,
    } as VideoUpdateTagsRequest);
    return response.data;
  },

  async getTranscript(videoId: string): Promise<TranscriptDetail> {
    const response = await apiClient.get(`/videos/${videoId}/transcript`);
    return response.data;
  },

  async getCollections(videoId: string): Promise<{ collection_ids: string[] }> {
    const response = await apiClient.get(`/videos/${videoId}/collections`);
    return response.data;
  },

  async reprocess(videoId: string): Promise<{ video_id: string; job_id: string; status: string; message: string }> {
    const response = await apiClient.post(`/videos/${videoId}/reprocess`);
    return response.data;
  },

  async cancel(videoId: string, cleanupOption: CleanupOption = "keep_video"): Promise<VideoCancelResponse> {
    const request: VideoCancelRequest = { cleanup_option: cleanupOption };
    const response = await apiClient.post(`/videos/${videoId}/cancel`, request);
    return response.data;
  },

  async cancelBulk(videoIds: string[], cleanupOption: CleanupOption = "keep_video"): Promise<BulkCancelResponse> {
    const request: BulkCancelRequest = { video_ids: videoIds, cleanup_option: cleanupOption };
    const response = await apiClient.post("/videos/cancel-bulk", request);
    return response.data;
  },

  async bulkUpdateTags(videoIds: string[], addTags: string[], removeTags: string[]): Promise<{ updated: number; total: number; message: string }> {
    const response = await apiClient.patch("/videos/tags/bulk", {
      video_ids: videoIds,
      add_tags: addTags,
      remove_tags: removeTags,
    });
    return response.data;
  },

  async getSimilar(videoId: string, limit: number = 5): Promise<SimilarVideosResponse> {
    const response = await apiClient.get(`/videos/${videoId}/similar`, {
      params: { limit },
    });
    return response.data;
  },
};
