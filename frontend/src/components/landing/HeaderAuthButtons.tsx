'use client';

import { useSafeAuthState } from '@/lib/auth/safe-hooks';

/**
 * Auth-aware header buttons for landing page
 * Shows Sign In/Get Started for guests, or user menu for authenticated users
 */
export default function HeaderAuthButtons() {
  const { isAuthenticated, isLoading, user } = useSafeAuthState();

  // Show nothing while loading to prevent flash
  if (isLoading) {
    return (
      <div className="flex items-center gap-4">
        <div className="w-16 h-4 bg-gray-200 rounded animate-pulse" />
        <div className="w-24 h-10 bg-gray-200 rounded-lg animate-pulse" />
      </div>
    );
  }

  if (isAuthenticated && user) {
    return (
      <div className="flex items-center gap-4">
        <a
          href="/videos"
          className="text-gray-600 hover:text-primary transition-colors"
        >
          Dashboard
        </a>
        <a
          href="/account"
          className="bg-primary text-white px-6 py-2 rounded-lg hover:bg-primary-light transition-colors"
        >
          {user.displayName || user.email?.split('@')[0] || 'Account'}
        </a>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-4">
      <a
        href="/login"
        className="text-gray-600 hover:text-primary transition-colors"
      >
        Sign In
      </a>
      <a
        href="/login"
        className="bg-primary text-white px-6 py-2 rounded-lg hover:bg-primary-light transition-colors"
      >
        Get Started
      </a>
    </div>
  );
}
