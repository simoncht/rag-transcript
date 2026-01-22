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
            Transform YouTube Videos into
            <br />
            <span className="text-primary">Searchable Knowledge</span>
          </h1>

          {/* Subheadline */}
          <p className="text-xl lg:text-2xl text-gray-600 mb-8 max-w-3xl mx-auto">
            AI-powered transcription, semantic search, and conversation memory
            for your video library. Chat with your videos and get precise,
            cited answers.
          </p>

          {/* CTAs */}
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <Button
              variant="primary"
              size="lg"
              onClick={() => (window.location.href = '/login')}
              className="w-full sm:w-auto"
            >
              Start Free
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
              View Pricing
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
              <span>Free tier available</span>
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
              <span>Cancel anytime</span>
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
