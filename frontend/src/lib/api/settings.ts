import { apiClient } from "./client";
import { EmbeddingSettingsResponse } from "../types";

export const settingsApi = {
  async getEmbeddingSettings(): Promise<EmbeddingSettingsResponse> {
    const response = await apiClient.get("/settings/embedding-model");
    return response.data;
  },
  async setEmbeddingModel(modelKey: string): Promise<EmbeddingSettingsResponse> {
    const response = await apiClient.post("/settings/embedding-model", {
      model_key: modelKey,
    });
    return response.data;
  },
};
