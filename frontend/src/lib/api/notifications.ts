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
    offset = 0,
    limit = 20,
    includeRead = true
  ): Promise<NotificationListResponse> {
    const params: Record<string, string | number | boolean> = {
      offset,
      limit,
      include_read: includeRead,
    };

    const response = await apiClient.get("/notifications", { params });
    return response.data;
  },

  async getUnreadCount(): Promise<{ unread_count: number }> {
    const response = await apiClient.get("/notifications/unread-count");
    return response.data;
  },

  async markRead(notificationId: string): Promise<{ marked_count: number }> {
    const response = await apiClient.post("/notifications/mark-read", {
      notification_ids: [notificationId],
    });
    return response.data;
  },

  async markAllRead(): Promise<{ marked_count: number }> {
    const response = await apiClient.post("/notifications/mark-read", {
      notification_ids: [],
    });
    return response.data;
  },

  async dismiss(notificationId: string): Promise<{ dismissed_count: number }> {
    const response = await apiClient.post("/notifications/dismiss", {
      notification_ids: [notificationId],
    });
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
  ): Promise<{ updated: number }> {
    const response = await apiClient.put("/notifications/preferences", {
      preferences: [
        {
          event_type_id: eventTypeId,
          ...request,
        },
      ],
    });
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
    const response = await apiClient.put("/notifications/settings", request);
    return response.data;
  },
};
