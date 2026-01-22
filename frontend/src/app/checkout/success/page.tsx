'use client';

import React, { Suspense, useEffect, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { subscriptionsApi } from '@/lib/api/subscriptions';
import Card from '@/components/shared/Card';
import Button from '@/components/shared/Button';
import { MainLayout } from '@/components/layout/MainLayout';

/**
 * Checkout Success Page - Post-purchase confirmation
 * Extracts session_id from URL, shows success message and new quota
 */
function CheckoutSuccessContent() {
  const searchParams = useSearchParams();
  const sessionId = searchParams.get('session_id');
  const queryClient = useQueryClient();
  const [showConfetti, setShowConfetti] = useState(false);

  // Fetch updated quota to confirm upgrade
  const { data: quota, isLoading } = useQuery({
    queryKey: ['subscription-quota'],
    queryFn: subscriptionsApi.getQuota,
    enabled: !!sessionId,
  });

  // Invalidate queries to refresh subscription data
  useEffect(() => {
    if (sessionId) {
      // Invalidate all subscription-related queries
      queryClient.invalidateQueries({ queryKey: ['subscription-quota'] });
      queryClient.invalidateQueries({ queryKey: ['current-subscription'] });

      // Show confetti effect
      setShowConfetti(true);
      const timer = setTimeout(() => setShowConfetti(false), 5000);
      return () => clearTimeout(timer);
    }
  }, [sessionId, queryClient]);

  if (!sessionId) {
    return (
      <MainLayout>
        <div className="max-w-2xl mx-auto px-4 py-12">
          <Card className="text-center py-12">
            <div className="flex items-center justify-center w-16 h-16 rounded-full bg-yellow-100 mb-6 mx-auto">
              <svg
                className="w-8 h-8 text-yellow-600"
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
            <h2 className="text-2xl font-bold text-gray-900 mb-4">
              Invalid Session
            </h2>
            <p className="text-gray-600 mb-6">
              No checkout session found. If you completed a purchase, please check your email for confirmation.
            </p>
            <Button onClick={() => (window.location.href = '/account')}>
              Go to Account
            </Button>
          </Card>
        </div>
      </MainLayout>
    );
  }

  return (
    <MainLayout>
      <div className="max-w-2xl mx-auto px-4 py-12">
        {/* Confetti effect */}
        {showConfetti && (
          <div className="fixed inset-0 pointer-events-none z-50 overflow-hidden">
            {[...Array(50)].map((_, i) => (
              <div
                key={i}
                className="absolute animate-confetti"
                style={{
                  left: `${Math.random() * 100}%`,
                  top: `-${Math.random() * 20}%`,
                  animationDelay: `${Math.random() * 2}s`,
                  animationDuration: `${3 + Math.random() * 2}s`,
                }}
              >
                <div
                  className="w-2 h-2 rounded-full"
                  style={{
                    backgroundColor: ['#10B981', '#3B82F6', '#F59E0B', '#EF4444', '#8B5CF6'][
                      Math.floor(Math.random() * 5)
                    ],
                  }}
                />
              </div>
            ))}
          </div>
        )}

        {/* Success card */}
        <Card className="text-center py-12">
          <div className="flex items-center justify-center w-20 h-20 rounded-full bg-green-100 mb-6 mx-auto">
            <svg
              className="w-10 h-10 text-green-600"
              fill="none"
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth="2"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path d="M5 13l4 4L19 7" />
            </svg>
          </div>

          <h1 className="text-3xl font-bold text-gray-900 mb-4">
            Payment Successful!
          </h1>
          <p className="text-xl text-gray-600 mb-8">
            Welcome to {quota?.tier ? quota.tier.charAt(0).toUpperCase() + quota.tier.slice(1) : 'Pro'}! Your upgrade is now active.
          </p>

          {/* New quota display */}
          {isLoading ? (
            <div className="flex items-center justify-center py-8">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
            </div>
          ) : quota ? (
            <div className="bg-gray-50 rounded-lg p-6 mb-8">
              <h3 className="font-semibold text-gray-900 mb-4">
                Your New Limits:
              </h3>
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div className="text-center">
                  <p className="text-gray-600 mb-1">Videos</p>
                  <p className="text-2xl font-bold text-green-600">
                    {quota.videos_limit === -1 ? '∞' : quota.videos_limit}
                  </p>
                </div>
                <div className="text-center">
                  <p className="text-gray-600 mb-1">Messages/month</p>
                  <p className="text-2xl font-bold text-green-600">
                    {quota.messages_limit === -1 ? '∞' : quota.messages_limit.toLocaleString()}
                  </p>
                </div>
                <div className="text-center">
                  <p className="text-gray-600 mb-1">Storage</p>
                  <p className="text-2xl font-bold text-green-600">
                    {quota.storage_limit_mb === -1 ? '∞' : `${quota.storage_limit_mb / 1024} GB`}
                  </p>
                </div>
                <div className="text-center">
                  <p className="text-gray-600 mb-1">Minutes/month</p>
                  <p className="text-2xl font-bold text-green-600">
                    {quota.minutes_limit === -1 ? '∞' : quota.minutes_limit.toLocaleString()}
                  </p>
                </div>
              </div>
            </div>
          ) : null}

          {/* Call to action */}
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Button
              variant="primary"
              size="lg"
              onClick={() => (window.location.href = '/videos')}
            >
              Start Uploading Videos
            </Button>
            <Button
              variant="outline"
              size="lg"
              onClick={() => (window.location.href = '/account')}
            >
              View Account
            </Button>
          </div>

          {/* Additional info */}
          <p className="text-sm text-gray-500 mt-8">
            A confirmation email has been sent to your inbox.
          </p>
        </Card>
      </div>

      {/* Confetti animation styles */}
      <style jsx>{`
        @keyframes confetti {
          to {
            transform: translateY(100vh) rotate(360deg);
          }
        }
        .animate-confetti {
          animation: confetti linear forwards;
        }
      `}</style>
    </MainLayout>
  );
}

export default function CheckoutSuccessPage() {
  return (
    <Suspense fallback={
      <MainLayout>
        <div className="max-w-2xl mx-auto px-4 py-12">
          <Card className="text-center py-12">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto" />
          </Card>
        </div>
      </MainLayout>
    }>
      <CheckoutSuccessContent />
    </Suspense>
  );
}
