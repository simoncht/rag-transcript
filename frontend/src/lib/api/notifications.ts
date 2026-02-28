import { apiClient } from "./client";
import {
  Notification,
  NotificationListResponse,
  NotificationPreference,
  NotificationPreferencesResponse,
  NotificationPreferenceUpdateRequest,
  NotificationSettings,
  NotificationSettingsUpdateRequest,
} from "../types";

export const notificationsApi = {
  // ==========================================
  // Notifications
  // ==========================================

  async list(
    skip = 0,
    limit = 20,
    unreadOnly = false
  ): Promise<NotificationListResponse> {
    const params: Record<string, string | number | boolean> = { skip, limit };
    if (unreadOnly) params.unread_only = true;

    const response = await apiClient.get("/notifications", { params });
    return response.data;
  },

  async getUnreadCount(): Promise<{ count: number }> {
    const response = await apiClient.get("/notifications/unread-count");
    return response.data;
  },

  async markRead(notificationId: string): Promise<Notification> {
    const response = await apiClient.post(
      `/notifications/${notificationId}/read`
    );
    return response.data;
  },

  async markAllRead(): Promise<{ marked: number }> {
    const response = await apiClient.post("/notifications/read-all");
    return response.data;
  },

  async dismiss(notificationId: string): Promise<Notification> {
    const response = await apiClient.post(
      `/notifications/${notificationId}/dismiss`
    );
    return response.data;
  },

  // ==========================================
  // Preferences
  // ==========================================

  async getPreferences(): Promise<NotificationPreferencesResponse> {
    const response = await apiClient.get("/notifications/preferences");
    return response.data;
  },

  async updatePreference(
    eventTypeId: string,
    request: NotificationPreferenceUpdateRequest
  ): Promise<NotificationPreference> {
    const response = await apiClient.patch(
      `/notifications/preferences/${eventTypeId}`,
      request
    );
    return response.data;
  },

  // ==========================================
  // Settings
  // ==========================================

  async getSettings(): Promise<NotificationSettings> {
    const response = await apiClient.get("/notifications/settings");
    return response.data;
  },

  async updateSettings(
    request: NotificationSettingsUpdateRequest
  ): Promise<NotificationSettings> {
    const response = await apiClient.patch("/notifications/settings", request);
    return response.data;
  },
};
