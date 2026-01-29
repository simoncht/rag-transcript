'use client';

import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { useAuthState } from '@/lib/auth';
import { MainLayout } from '@/components/layout/MainLayout';
import Card from '@/components/shared/Card';
import SubscriptionManager from '@/components/subscription/SubscriptionManager';
import { subscriptionsApi } from '@/lib/api/subscriptions';
import { useSetBreadcrumb } from '@/contexts/BreadcrumbContext';
import type { QuotaUsage, SubscriptionDetail } from '@/lib/types';

/**
 * Account Page - Account & Subscription management
 * Uses MainLayout, auth-protected route
 */
export default function AccountPage() {
  const authState = useAuthState();
  const { user, isAuthenticated } = authState;

  // Fetch quota - uses same query key as SubscriptionManager for cache sharing
  const { data: quota } = useQuery<QuotaUsage>({
    queryKey: ['subscription-quota'],
    queryFn: subscriptionsApi.getQuota,
    staleTime: 30 * 1000,
    enabled: isAuthenticated,
  });

  // Fetch subscription tier
  const { data: subscription } = useQuery<SubscriptionDetail | null>({
    queryKey: ['current-subscription'],
    queryFn: async () => {
      try {
        return await subscriptionsApi.getCurrentSubscription();
      } catch (error: unknown) {
        if (error && typeof error === 'object' && 'response' in error) {
          const axiosError = error as { response?: { status?: number } };
          if (axiosError.response?.status === 404) {
            return null;
          }
        }
        throw error;
      }
    },
    retry: false,
    enabled: isAuthenticated,
  });

  // Breadcrumb: subscription tier
  const breadcrumbDetail = subscription?.tier || (isAuthenticated ? 'free' : undefined);
  useSetBreadcrumb('account', breadcrumbDetail);

  // Show sign-in prompt if not authenticated
  if (!isAuthenticated) {
    return (
      <MainLayout>
        <div className="max-w-4xl mx-auto px-4 py-12">
          <Card className="text-center py-12">
            <h2 className="text-2xl font-bold text-gray-900 mb-4">
              Sign In Required
            </h2>
            <p className="text-gray-600 mb-6">
              Please sign in to manage your account and subscription.
            </p>
            <a
              href="/login"
              className="inline-block bg-primary text-white px-6 py-2 rounded-lg hover:bg-primary-light transition-colors"
            >
              Sign In
            </a>
          </Card>
        </div>
      </MainLayout>
    );
  }

  return (
    <MainLayout>
      <div className="max-w-5xl mx-auto px-4 py-8">
        {/* Page header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">
            Account & Subscription
          </h1>
          <p className="text-gray-600">
            Manage your account settings and subscription plan
          </p>
          {quota && (
            <div className="flex items-center gap-2 text-xs text-gray-500 pt-1">
              <span className="capitalize">{subscription?.tier || 'free'} plan</span>
              <span>•</span>
              <span>{quota.videos_used} video{quota.videos_used !== 1 ? 's' : ''}</span>
              <span>•</span>
              <span>{quota.messages_used} message{quota.messages_used !== 1 ? 's' : ''} this month</span>
            </div>
          )}
        </div>

        {/* User Info */}
        <Card className="mb-6">
          <h2 className="text-xl font-bold text-gray-900 mb-4">
            Account Information
          </h2>
          <div className="space-y-3 text-sm">
            <div className="flex justify-between">
              <span className="text-gray-600">Email:</span>
              <span className="font-medium text-gray-900">
                {user?.email || 'Not available'}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">Name:</span>
              <span className="font-medium text-gray-900">
                {user?.displayName || 'Not set'}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">User ID:</span>
              <span className="font-medium text-gray-900 font-mono text-xs">
                {user?.id || 'Not available'}
              </span>
            </div>
          </div>
        </Card>

        {/* Subscription Manager */}
        <SubscriptionManager />
      </div>
    </MainLayout>
  );
}
