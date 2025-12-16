import { apiClient } from "./client";
import type {
  DashboardResponse,
  UserListResponse,
  UserDetail,
  UserUpdateRequest,
  QuotaOverrideRequest,
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
};
