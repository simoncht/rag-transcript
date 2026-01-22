'use client';

import React from 'react';
import Card from '@/components/shared/Card';
import Button from '@/components/shared/Button';
import { MainLayout } from '@/components/layout/MainLayout';

/**
 * Checkout Cancel Page - Shown when user cancels payment
 */
export default function CheckoutCancelPage() {
  return (
    <MainLayout>
      <div className="max-w-2xl mx-auto px-4 py-12">
        <Card className="text-center py-12">
          <div className="flex items-center justify-center w-16 h-16 rounded-full bg-gray-100 mb-6 mx-auto">
            <svg
              className="w-8 h-8 text-gray-600"
              fill="none"
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth="2"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path d="M6 18L18 6M6 6l12 12" />
            </svg>
          </div>

          <h1 className="text-3xl font-bold text-gray-900 mb-4">
            Checkout Canceled
          </h1>
          <p className="text-xl text-gray-600 mb-8">
            No charges have been made to your account.
          </p>

          <div className="bg-gray-50 rounded-lg p-6 mb-8 text-left">
            <h3 className="font-semibold text-gray-900 mb-3">
              Changed your mind?
            </h3>
            <p className="text-gray-600 text-sm mb-4">
              You can still enjoy the free tier, which includes:
            </p>
            <ul className="space-y-2 text-sm text-gray-600">
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
                <span>2 videos</span>
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
                <span>50 messages per month</span>
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
                <span>1 GB storage</span>
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
                <span>120 minutes per month</span>
              </li>
            </ul>
          </div>

          {/* Call to action */}
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Button
              variant="primary"
              size="lg"
              onClick={() => (window.location.href = '/pricing')}
            >
              View Pricing Again
            </Button>
            <Button
              variant="outline"
              size="lg"
              onClick={() => (window.location.href = '/videos')}
            >
              Continue with Free Plan
            </Button>
          </div>

          {/* Support link */}
          <p className="text-sm text-gray-500 mt-8">
            Have questions?{' '}
            <a
              href="mailto:support@example.com"
              className="text-primary hover:underline"
            >
              Contact support
            </a>
          </p>
        </Card>
      </div>
    </MainLayout>
  );
}
