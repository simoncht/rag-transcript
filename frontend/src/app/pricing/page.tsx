import React from 'react';
import type { Metadata } from 'next';
import PricingComparison from '@/components/subscription/PricingComparison';

export const metadata: Metadata = {
  title: 'Pricing - RAG Transcript',
  description: 'Simple, transparent pricing for AI-powered video knowledge base. Start free, upgrade anytime.',
};

/**
 * Pricing Page - Standalone pricing page (no MainLayout)
 * Public route (works without auth)
 */
export default function PricingPage() {
  return (
    <div className="min-h-screen bg-gradient-to-b from-white to-gray-50">
      {/* Header */}
      <header className="border-b border-gray-200 bg-white/80 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <a href="/" className="text-2xl font-bold text-primary">
              RAG Transcript
            </a>
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
          </div>
        </div>
      </header>

      {/* Main content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
        {/* Hero section */}
        <div className="text-center mb-16">
          <h1 className="text-5xl font-bold text-gray-900 mb-4">
            Simple, Transparent Pricing
          </h1>
          <p className="text-xl text-gray-600 max-w-2xl mx-auto">
            Start free, upgrade anytime. No hidden fees, no surprises.
          </p>
        </div>

        {/* Pricing comparison */}
        <PricingComparison />

        {/* FAQ preview */}
        <div className="mt-20 text-center">
          <h2 className="text-3xl font-bold text-gray-900 mb-4">
            Frequently Asked Questions
          </h2>
          <p className="text-gray-600 mb-8">
            Have questions? Check out our{' '}
            <a href="/#faq" className="text-primary hover:underline">
              FAQ section
            </a>
            {' '}or{' '}
            <a href="mailto:support@example.com" className="text-primary hover:underline">
              contact us
            </a>
          </p>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-gray-200 bg-white mt-20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="text-center text-gray-500 text-sm">
            <p>&copy; {new Date().getFullYear()} RAG Transcript. All rights reserved.</p>
          </div>
        </div>
      </footer>
    </div>
  );
}
