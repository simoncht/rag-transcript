'use client';

import React, { useState } from 'react';
import Button from '../shared/Button';
import { subscriptionsApi } from '@/lib/api/subscriptions';

type QuotaType = 'videos' | 'messages' | 'storage' | 'minutes';

interface UpgradePromptModalProps {
  quotaType: QuotaType;
  isOpen: boolean;
  onClose: () => void;
}

const quotaLabels = {
  videos: 'video',
  messages: 'message',
  storage: 'storage',
  minutes: 'transcription minute',
};

/**
 * UpgradePromptModal - Modal shown when quota is exceeded
 * Handles upgrade flow via Stripe checkout
 */
export default function UpgradePromptModal({
  quotaType,
  isOpen,
  onClose,
}: UpgradePromptModalProps) {
  const [isLoading, setIsLoading] = useState(false);

  const handleUpgrade = async () => {
    setIsLoading(true);
    try {
      const { checkout_url } = await subscriptionsApi.createCheckoutSession({
        tier: 'pro',
        success_url: `${window.location.origin}/checkout/success?session_id={CHECKOUT_SESSION_ID}`,
        cancel_url: `${window.location.origin}/checkout/cancel`,
      });
      window.location.href = checkout_url;
    } catch (error) {
      console.error('Failed to create checkout session:', error);
      alert('Failed to start upgrade process. Please try again.');
      setIsLoading(false);
    }
  };

  const handleViewPricing = () => {
    window.location.href = '/pricing';
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="relative bg-white rounded-lg shadow-xl max-w-md w-full mx-4 p-6">
        {/* Header */}
        <div className="mb-6">
          <div className="flex items-center justify-center w-12 h-12 rounded-full bg-yellow-100 mb-4 mx-auto">
            <svg
              className="w-6 h-6 text-yellow-600"
              fill="none"
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth="2"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
          </div>
          <h2 className="text-2xl font-bold text-gray-900 text-center mb-2">
            {quotaLabels[quotaType].charAt(0).toUpperCase() + quotaLabels[quotaType].slice(1)} Limit Reached
          </h2>
          <p className="text-gray-600 text-center">
            You&apos;ve reached your {quotaLabels[quotaType]} limit. Upgrade to continue.
          </p>
        </div>

        {/* Benefits */}
        <div className="mb-6 bg-gray-50 rounded-lg p-4">
          <p className="font-semibold text-gray-900 mb-3">
            Upgrade to Pro for:
          </p>
          <ul className="space-y-2">
            <li className="flex items-start gap-2">
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
              <span className="text-gray-700 text-sm">Unlimited videos</span>
            </li>
            <li className="flex items-start gap-2">
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
              <span className="text-gray-700 text-sm">1,000 messages per month</span>
            </li>
            <li className="flex items-start gap-2">
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
              <span className="text-gray-700 text-sm">10 GB storage</span>
            </li>
            <li className="flex items-start gap-2">
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
              <span className="text-gray-700 text-sm">1,200 minutes per month</span>
            </li>
          </ul>
        </div>

        {/* Actions */}
        <div className="flex flex-col sm:flex-row gap-3">
          <Button
            variant="primary"
            size="lg"
            onClick={handleUpgrade}
            isLoading={isLoading}
            className="flex-1"
          >
            Upgrade to Pro
          </Button>
          <Button
            variant="outline"
            size="lg"
            onClick={handleViewPricing}
            className="flex-1"
          >
            View Pricing
          </Button>
        </div>

        {/* Cancel link */}
        <button
          onClick={onClose}
          className="mt-4 text-sm text-gray-500 hover:text-gray-700 w-full text-center"
        >
          Maybe later
        </button>
      </div>
    </div>
  );
}
