'use client';

import { Suspense, useEffect, useState } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { subscriptionsApi } from '@/lib/api/subscriptions';
import { useSafeAuthState } from '@/lib/auth/safe-hooks';
import { SubscriptionTier } from '@/lib/types';

function CheckoutContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const { isAuthenticated } = useSafeAuthState();
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const tier = searchParams.get('tier') as SubscriptionTier | null;

  useEffect(() => {
    // Wait for auth state to be determined
    if (!isAuthenticated) {
      // Give it a moment to load auth state
      const timeout = setTimeout(() => {
        if (!isAuthenticated) {
          // Still not authenticated, redirect to login
          router.push(`/login?callbackUrl=${encodeURIComponent(window.location.href)}`);
        }
      }, 2000);
      return () => clearTimeout(timeout);
    }

    // Validate tier
    if (!tier || !['pro', 'enterprise'].includes(tier)) {
      setError('Invalid subscription tier');
      setIsLoading(false);
      return;
    }

    // Initiate checkout
    const startCheckout = async () => {
      try {
        const { checkout_url } = await subscriptionsApi.createCheckoutSession({
          tier,
          success_url: `${window.location.origin}/checkout/success?session_id={CHECKOUT_SESSION_ID}`,
          cancel_url: `${window.location.origin}/checkout/cancel`,
        });

        // Redirect to Stripe checkout
        window.location.href = checkout_url;
      } catch (err) {
        console.error('Failed to create checkout session:', err);
        setError('Failed to start checkout. Please try again.');
        setIsLoading(false);
      }
    };

    startCheckout();
  }, [isAuthenticated, tier, router]);

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <p className="text-red-600 mb-4">{error}</p>
          <button
            onClick={() => router.push('/#pricing')}
            className="text-primary hover:underline"
          >
            Return to pricing
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="text-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto mb-4" />
        <p className="text-gray-600">
          {isLoading ? 'Preparing checkout...' : 'Redirecting to payment...'}
        </p>
      </div>
    </div>
  );
}

function CheckoutFallback() {
  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="text-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto mb-4" />
        <p className="text-gray-600">Loading...</p>
      </div>
    </div>
  );
}

/**
 * Checkout Start Page
 *
 * Automatically initiates Stripe checkout after user signs in.
 * Expects ?tier=pro or ?tier=enterprise query parameter.
 */
export default function CheckoutStartPage() {
  return (
    <Suspense fallback={<CheckoutFallback />}>
      <CheckoutContent />
    </Suspense>
  );
}
