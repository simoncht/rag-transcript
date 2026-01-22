'use client';

import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { subscriptionsApi } from '@/lib/api/subscriptions';
import { useSafeAuthState } from '@/lib/auth/safe-hooks';
import PricingCard from './PricingCard';
import { SubscriptionTier } from '@/lib/types';

interface PricingComparisonProps {
  onUpgrade?: (tier: SubscriptionTier) => void;
  className?: string;
}

/**
 * PricingComparison - 3-tier comparison with monthly/yearly toggle
 * Fetches pricing via React Query
 * Grid layout (3 cols on lg, 1 col on mobile)
 */
export default function PricingComparison({
  onUpgrade,
  className = '',
}: PricingComparisonProps) {
  const [billingCycle, setBillingCycle] = useState<'monthly' | 'yearly'>('monthly');
  const { isAuthenticated } = useSafeAuthState();

  // Fetch pricing tiers
  const { data: tiers, isLoading, error } = useQuery({
    queryKey: ['pricing-tiers'],
    queryFn: subscriptionsApi.getPricing,
    staleTime: 10 * 60 * 1000, // 10 minutes
  });

  // Fetch current subscription if authenticated
  const { data: currentSubscription } = useQuery({
    queryKey: ['current-subscription'],
    queryFn: subscriptionsApi.getCurrentSubscription,
    enabled: isAuthenticated,
    retry: false, // Don't retry if user has no subscription
  });

  if (isLoading) {
    return (
      <div className={`flex items-center justify-center py-12 ${className}`}>
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary" />
      </div>
    );
  }

  if (error) {
    return (
      <div className={`text-center py-12 ${className}`}>
        <p className="text-red-600 mb-4">Failed to load pricing information</p>
        <button
          onClick={() => window.location.reload()}
          className="text-primary hover:underline"
        >
          Retry
        </button>
      </div>
    );
  }

  if (!tiers || tiers.length === 0) {
    return (
      <div className={`text-center py-12 ${className}`}>
        <p className="text-gray-500">No pricing tiers available</p>
      </div>
    );
  }

  // Sort tiers: free, pro, enterprise
  const sortedTiers = [...tiers].sort((a, b) => {
    const order = { free: 0, pro: 1, enterprise: 2 };
    return order[a.tier] - order[b.tier];
  });

  return (
    <div className={className}>
      {/* Billing cycle toggle */}
      <div className="flex items-center justify-center gap-4 mb-12">
        <button
          onClick={() => setBillingCycle('monthly')}
          className={`
            px-6 py-2 rounded-lg font-medium transition-all
            ${
              billingCycle === 'monthly'
                ? 'bg-primary text-white'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }
          `}
        >
          Monthly
        </button>
        <button
          onClick={() => setBillingCycle('yearly')}
          className={`
            px-6 py-2 rounded-lg font-medium transition-all relative
            ${
              billingCycle === 'yearly'
                ? 'bg-primary text-white'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }
          `}
        >
          Yearly
          <span className="ml-2 text-xs bg-green-500 text-white px-2 py-0.5 rounded-full">
            Save 20%
          </span>
        </button>
      </div>

      {/* Pricing cards grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8 lg:gap-6 items-stretch">
        {sortedTiers.map((tier) => (
          <div key={tier.tier} className="flex">
            <PricingCard
              tier={tier}
              billingCycle={billingCycle}
              currentTier={currentSubscription?.tier}
              isAuthenticated={isAuthenticated}
              onUpgrade={onUpgrade}
              className="w-full"
            />
          </div>
        ))}
      </div>

      {/* Additional info */}
      <div className="text-center mt-12 text-sm text-gray-500">
        <p>All plans include AI-powered transcription and semantic search</p>
        <p className="mt-2">
          Need a custom plan?{' '}
          <a href="mailto:support@example.com" className="text-primary hover:underline">
            Contact us
          </a>
        </p>
      </div>
    </div>
  );
}
