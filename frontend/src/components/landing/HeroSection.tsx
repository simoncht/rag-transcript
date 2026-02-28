'use client';

import React from 'react';
import Button from '../shared/Button';

/**
 * HeroSection - Landing page hero with headline and CTAs
 */
export default function HeroSection() {
  return (
    <section className="relative py-20 lg:py-32">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center">
          {/* Headline */}
          <h1 className="text-5xl lg:text-6xl font-bold text-gray-900 mb-6">
            The Answer Is in There Somewhere.
            <br />
            <span className="text-primary">Until Now.</span>
          </h1>

          {/* Loss framing - personally verifiable, no dubious stats */}
          <p className="text-base lg:text-lg text-gray-500 mb-4 max-w-2xl mx-auto">
            You&apos;ve consumed hundreds of hours of content. Without the right
            tool, most of that knowledge is gone the moment you close the tab.
          </p>

          {/* Subheadline */}
          <p className="text-xl lg:text-2xl text-gray-600 mb-8 max-w-3xl mx-auto">
            Add a video or document. Ask any question about what&apos;s inside. Get
            the exact answer with a citation that proves it. Every time.
          </p>

          {/* CTAs */}
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <Button
              variant="primary"
              size="lg"
              onClick={() => (window.location.href = '/get-started')}
              className="w-full sm:w-auto"
            >
              Find Your First Answer Free
            </Button>
            <Button
              variant="outline"
              size="lg"
              onClick={() => {
                const pricingSection = document.getElementById('pricing');
                if (pricingSection) {
                  pricingSection.scrollIntoView({ behavior: 'smooth' });
                } else {
                  window.location.href = '/pricing';
                }
              }}
              className="w-full sm:w-auto"
            >
              See What&apos;s Included
            </Button>
          </div>

          {/* Trust indicators */}
          <div className="mt-12 flex flex-wrap items-center justify-center gap-8 text-sm text-gray-500">
            <div className="flex items-center gap-2">
              <svg
                className="w-5 h-5 text-green-500"
                fill="none"
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="2"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path d="M5 13l4 4L19 7" />
              </svg>
              <span>No credit card required</span>
            </div>
            <div className="flex items-center gap-2">
              <svg
                className="w-5 h-5 text-green-500"
                fill="none"
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="2"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path d="M5 13l4 4L19 7" />
              </svg>
              <span>10 videos + 50 documents free</span>
            </div>
            <div className="flex items-center gap-2">
              <svg
                className="w-5 h-5 text-green-500"
                fill="none"
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="2"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path d="M5 13l4 4L19 7" />
              </svg>
              <span>14-day money-back guarantee</span>
            </div>
          </div>
        </div>
      </div>

      {/* Decorative background elements */}
      <div className="absolute inset-0 -z-10 overflow-hidden">
        <div className="absolute left-1/4 top-20 w-72 h-72 bg-primary/5 rounded-full blur-3xl" />
        <div className="absolute right-1/4 bottom-20 w-96 h-96 bg-secondary/5 rounded-full blur-3xl" />
      </div>
    </section>
  );
}
