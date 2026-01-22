'use client';

import React from 'react';
import PricingComparison from '../subscription/PricingComparison';

/**
 * PricingSection - Wrapper around PricingComparison for landing page
 */
export default function PricingSection() {
  return (
    <section id="pricing" className="py-20 bg-white">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Section header */}
        <div className="text-center mb-16">
          <h2 className="text-4xl font-bold text-gray-900 mb-4">
            Simple, Transparent Pricing
          </h2>
          <p className="text-xl text-gray-600 max-w-2xl mx-auto">
            Start free, upgrade anytime. No hidden fees, no surprises.
          </p>
        </div>

        {/* Pricing comparison */}
        <PricingComparison />
      </div>
    </section>
  );
}
