'use client';

import React from 'react';
import Card from '../shared/Card';
import Button from '../shared/Button';
import Badge from '../shared/Badge';
import { PricingTier, SubscriptionTier } from '@/lib/types';

interface PricingCardProps {
  tier: PricingTier;
  billingCycle: 'monthly' | 'yearly';
  currentTier?: SubscriptionTier;
  isAuthenticated?: boolean;
  onUpgrade?: (tier: SubscriptionTier) => void;
  isLoading?: boolean;
  className?: string;
}

/**
 * PricingCard - Individual tier card with price, features, and CTA
 * Handles authenticated vs unauthenticated CTAs
 * Shows "Current Plan" badge if already on tier
 */
export default function PricingCard({
  tier,
  billingCycle,
  currentTier,
  isAuthenticated = false,
  onUpgrade,
  isLoading = false,
  className = '',
}: PricingCardProps) {
  const isCurrentTier = currentTier === tier.tier;
  const isFree = tier.tier === 'free';

  // Calculate display price
  const price = billingCycle === 'monthly' ? tier.price_monthly : tier.price_yearly;
  const displayPrice = price === 0 ? 'Free' : `$${(price / 100).toFixed(0)}`;
  const priceInterval = billingCycle === 'monthly' ? '/month' : '/year';

  // Determine CTA text and action
  const getCtaText = () => {
    if (isCurrentTier) return 'Current Plan';
    if (isFree) {
      // Only show "Current Plan" if authenticated AND we have subscription data
      // (currentTier being defined means the subscription query succeeded)
      // This prevents showing "Current Plan" during auth loading state
      if (isAuthenticated && currentTier !== undefined) {
        return 'Current Plan';
      }
      return 'Get Started';
    }
    // Always show "Upgrade to X" for paid tiers, regardless of auth status
    return `Upgrade to ${tier.name}`;
  };

  const handleCtaClick = () => {
    if (isCurrentTier) return;

    if (!isAuthenticated) {
      if (isFree) {
        // Free tier: just sign up/sign in, redirect to videos after
        window.location.href = `/login?callbackUrl=${encodeURIComponent('/videos')}`;
      } else {
        // Paid tiers: redirect to checkout after auth
        const callbackUrl = `/checkout/start?tier=${tier.tier}`;
        window.location.href = `/login?callbackUrl=${encodeURIComponent(callbackUrl)}`;
      }
      return;
    }

    // Trigger upgrade flow (for paid tiers)
    if (onUpgrade) {
      onUpgrade(tier.tier);
    }
  };

  // Highlight recommended tier (Pro)
  const isRecommended = tier.tier === 'pro';

  return (
    <Card
      className={`
        relative flex flex-col h-full
        ${isRecommended ? 'border-2 border-primary shadow-lg' : ''}
        ${className}
      `}
      hoverable={!isCurrentTier}
    >
      {/* Recommended badge */}
      {isRecommended && (
        <div className="absolute -top-4 left-1/2 transform -translate-x-1/2">
          <Badge variant="info">Recommended</Badge>
        </div>
      )}

      {/* Current plan badge */}
      {isCurrentTier && (
        <div className="absolute -top-4 left-1/2 transform -translate-x-1/2">
          <Badge variant="success">Current Plan</Badge>
        </div>
      )}

      {/* Header */}
      <div className="text-center mb-6">
        <h3 className="text-2xl font-bold text-gray-900 mb-2">{tier.name}</h3>
        <div className="flex items-baseline justify-center gap-1">
          <span className="text-4xl font-bold text-gray-900">{displayPrice}</span>
          {!isFree && <span className="text-gray-500">{priceInterval}</span>}
        </div>
        {billingCycle === 'yearly' && !isFree && (
          <p className="text-sm text-green-600 mt-1">
            Save ${((tier.price_monthly * 12 - tier.price_yearly) / 100).toFixed(0)}/year
          </p>
        )}
      </div>

      {/* Features */}
      <ul className="space-y-3 mb-8 flex-grow">
        {tier.features.map((feature, index) => (
          <li key={index} className="flex items-start gap-2">
            <svg
              className="w-5 h-5 text-green-500 flex-shrink-0 mt-0.5"
              fill="none"
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth="2"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path d="M5 13l4 4L19 7" />
            </svg>
            <span className="text-gray-600 text-sm">{feature}</span>
          </li>
        ))}
      </ul>

      {/* AI Model info */}
      <div className="border-t border-gray-200 pt-4 mb-4">
        <div className="flex items-start gap-2">
          <svg
            className="w-5 h-5 text-primary flex-shrink-0 mt-0.5"
            fill="none"
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth="2"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
          </svg>
          <div>
            <p className="font-medium text-gray-900 text-sm">
              {isFree ? 'Chat Model' : 'Reasoner Model'}
            </p>
            <p className="text-xs text-gray-500">
              {isFree
                ? 'Fast responses for quick questions and simple summaries'
                : 'Thinks step-by-step for complex analysis and finding patterns'}
            </p>
          </div>
        </div>
      </div>

      {/* Quota limits */}
      <div className="border-t border-gray-200 pt-4 mb-6 space-y-2 text-sm text-gray-500">
        <div className="flex justify-between">
          <span>Videos:</span>
          <span className="font-medium text-gray-700">
            {tier.video_limit === -1 ? 'Unlimited' : tier.video_limit}
          </span>
        </div>
        <div className="flex justify-between">
          <span>Messages:</span>
          <span className="font-medium text-gray-700">
            {tier.message_limit === -1 ? 'Unlimited' : `${tier.message_limit}/month`}
          </span>
        </div>
        <div className="flex justify-between">
          <span>Storage:</span>
          <span className="font-medium text-gray-700">
            {tier.storage_limit_mb === -1 ? 'Unlimited' : `${Math.round(tier.storage_limit_mb / 1000)} GB`}
          </span>
        </div>
        <div className="flex justify-between">
          <span>Minutes:</span>
          <span className="font-medium text-gray-700">
            {tier.minutes_limit === -1 ? 'Unlimited' : `${tier.minutes_limit}/month`}
          </span>
        </div>
      </div>

      {/* CTA Button */}
      <Button
        variant={isRecommended ? 'primary' : 'outline'}
        size="lg"
        onClick={handleCtaClick}
        disabled={isCurrentTier || isLoading}
        isLoading={isLoading && !isCurrentTier && tier.tier !== 'free'}
        className="w-full"
      >
        {getCtaText()}
      </Button>
    </Card>
  );
}
