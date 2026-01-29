import { apiClient } from "./client";
import {
  QuotaUsage,
  PricingTier,
  SubscriptionDetail,
  CheckoutSessionRequest,
  CheckoutSessionResponse,
  CustomerPortalRequest,
  CustomerPortalResponse,
} from "../types";

export const subscriptionsApi = {
  /**
   * Get current user's quota usage
   */
  async getQuota(): Promise<QuotaUsage> {
    const response = await apiClient.get("/subscriptions/quota");
    return response.data;
  },

  /**
   * Get pricing tier information for all tiers
   */
  async getPricing(): Promise<PricingTier[]> {
    const response = await apiClient.get("/subscriptions/pricing");
    return response.data;
  },

  /**
   * Get current user's subscription details
   */
  async getCurrentSubscription(): Promise<SubscriptionDetail> {
    const response = await apiClient.get("/subscriptions/current");
    return response.data;
  },

  /**
   * Create a Stripe checkout session for upgrading to a tier
   */
  async createCheckoutSession(
    request: CheckoutSessionRequest
  ): Promise<CheckoutSessionResponse> {
    const response = await apiClient.post("/subscriptions/checkout", request);
    return response.data;
  },

  /**
   * Create a Stripe customer portal session for managing subscription
   */
  async createPortalSession(
    request: CustomerPortalRequest
  ): Promise<CustomerPortalResponse> {
    const response = await apiClient.post("/subscriptions/portal", request);
    return response.data;
  },

  /**
   * Verify a completed checkout session and get updated quota.
   * This synchronously verifies the session with Stripe, avoiding webhook race conditions.
   */
  async verifyCheckout(sessionId: string): Promise<QuotaUsage> {
    const response = await apiClient.get(`/subscriptions/verify-checkout?session_id=${sessionId}`);
    return response.data;
  },
};
