import { apiClient } from "./client";
import { UsageSummary } from "../types";

export const usageApi = {
  async getSummary(): Promise<UsageSummary> {
    const response = await apiClient.get("/usage/summary");
    return response.data;
  },
};
