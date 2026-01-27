'use client';

import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { subscriptionsApi } from '@/lib/api/subscriptions';
import Card from '../shared/Card';
import Button from '../shared/Button';
import Badge from '../shared/Badge';
import QuotaProgressBar from './QuotaProgressBar';
import { SubscriptionTier } from '@/lib/types';

/**
 * SubscriptionManager - Main subscription management component
 * Displays current tier, quota, and management buttons
 */
export default function SubscriptionManager() {
  const [isLoading, setIsLoading] = useState(false);

  // Fetch current subscription
  // 404 means user is on free tier (no subscription record), not an error
  const {
    data: subscription,
    isLoading: isLoadingSubscription,
    error: subscriptionError,
  } = useQuery({
    queryKey: ['current-subscription'],
    queryFn: async () => {
      try {
        return await subscriptionsApi.getCurrentSubscription();
      } catch (error: unknown) {
        // 404 = no subscription = free tier (not an error)
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
  });

  // Fetch quota usage
  const {
    data: quota,
    isLoading: isLoadingQuota,
    error: quotaError,
  } = useQuery({
    queryKey: ['subscription-quota'],
    queryFn: subscriptionsApi.getQuota,
    staleTime: 30 * 1000, // 30 seconds
    refetchInterval: 60 * 1000, // Refetch every 60 seconds
  });

  // Handle manage subscription (Stripe portal)
  const handleManageSubscription = async () => {
    setIsLoading(true);
    try {
      const { portal_url } = await subscriptionsApi.createPortalSession({
        return_url: window.location.href,
      });
      window.location.href = portal_url;
    } catch (error) {
      console.error('Failed to open Stripe portal:', error);
      alert('Failed to open subscription management. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  // Handle upgrade
  const handleUpgrade = (tier: SubscriptionTier) => {
    window.location.href = `/pricing?upgrade=${tier}`;
  };

  const isLoadingData = isLoadingSubscription || isLoadingQuota;
  // Only treat quota errors as critical - subscription 404 is handled as "free tier"
  const hasError = quotaError;

  if (isLoadingData) {
    return (
      <Card>
        <div className="flex items-center justify-center py-12">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary" />
        </div>
      </Card>
    );
  }

  if (hasError) {
    return (
      <Card>
        <div className="text-center py-12">
          <p className="text-red-600 mb-4">Failed to load subscription information</p>
          <Button onClick={() => window.location.reload()}>Retry</Button>
        </div>
      </Card>
    );
  }

  const isFree = subscription?.tier === 'free' || !subscription;
  const isPro = subscription?.tier === 'pro';
  const isEnterprise = subscription?.tier === 'enterprise';

  // Determine tier display name
  const tierName = subscription?.tier
    ? subscription.tier.charAt(0).toUpperCase() + subscription.tier.slice(1)
    : 'Free';

  // Format renewal date
  const renewalDate = subscription?.current_period_end
    ? new Date(subscription.current_period_end).toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
      })
    : null;

  return (
    <div className="space-y-6">
      {/* Current Plan */}
      <Card>
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-2xl font-bold text-gray-900 mb-2">
              Current Plan
            </h2>
            <div className="flex items-center gap-3">
              <Badge variant={isFree ? 'default' : 'success'}>
                {tierName} Tier
              </Badge>
              {subscription?.status && subscription.status !== 'active' && (
                <Badge variant="warning">{subscription.status}</Badge>
              )}
            </div>
          </div>

          {/* Action buttons */}
          <div className="flex items-center gap-3">
            {!isFree && (
              <Button
                variant="outline"
                onClick={handleManageSubscription}
                isLoading={isLoading}
              >
                Manage Subscription
              </Button>
            )}
            {!isEnterprise && (
              <Button
                variant="primary"
                onClick={() => handleUpgrade(isPro ? 'enterprise' : 'pro')}
              >
                {isPro ? 'Upgrade to Enterprise' : 'Upgrade to Pro'}
              </Button>
            )}
          </div>
        </div>

        {/* Billing info */}
        {renewalDate && (
          <div className="text-sm text-gray-600">
            {subscription?.cancel_at_period_end ? (
              <p>Your subscription will end on {renewalDate}</p>
            ) : (
              <p>Next billing date: {renewalDate}</p>
            )}
          </div>
        )}
      </Card>

      {/* Quota Usage */}
      {quota && (
        <Card>
          <h3 className="text-xl font-bold text-gray-900 mb-6">Quota Usage</h3>

          <div className="space-y-6">
            {/* Videos */}
            <QuotaProgressBar
              used={quota.videos_used}
              limit={quota.videos_limit}
              label="Videos"
              showDetails
            />

            {/* Messages */}
            <QuotaProgressBar
              used={quota.messages_used}
              limit={quota.messages_limit}
              label="Messages (this month)"
              showDetails
            />

            {/* Storage */}
            <QuotaProgressBar
              used={Math.round(quota.storage_used_mb)}
              limit={quota.storage_limit_mb}
              label="Storage (MB)"
              showDetails
            />

            {/* Minutes */}
            <QuotaProgressBar
              used={quota.minutes_used}
              limit={quota.minutes_limit}
              label="Transcription Minutes (this month)"
              showDetails
            />
          </div>

          {/* Quota warning */}
          {quota.videos_remaining === 0 && (
            <div className="mt-6 p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
              <p className="text-yellow-800 text-sm">
                You&apos;ve reached your video limit. Upgrade to add more videos.
              </p>
            </div>
          )}
        </Card>
      )}

      {/* Upgrade CTA for free users */}
      {isFree && (
        <Card className="bg-gradient-to-br from-primary/5 to-secondary/5">
          <div className="text-center py-8">
            <h3 className="text-2xl font-bold text-gray-900 mb-4">
              Ready for More?
            </h3>
            <p className="text-gray-600 mb-6 max-w-2xl mx-auto">
              Upgrade to Pro for unlimited videos, 1,000 messages/month, and
              10 GB storage. Perfect for power users and professionals.
            </p>
            <Button
              variant="primary"
              size="lg"
              onClick={() => handleUpgrade('pro')}
            >
              Upgrade to Pro
            </Button>
          </div>
        </Card>
      )}
    </div>
  );
}
