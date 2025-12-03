import { apiClient } from "./client";
import { Video, VideoListResponse } from "../types";

export const videosApi = {
  async list(skip = 0, limit = 50): Promise<VideoListResponse> {
    const response = await apiClient.get("/videos", {
      params: { skip, limit },
    });
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
};
