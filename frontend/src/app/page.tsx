import React from 'react';
import type { Metadata } from 'next';
import HeroSection from '@/components/landing/HeroSection';
import FeaturesSection from '@/components/landing/FeaturesSection';
import PricingSection from '@/components/landing/PricingSection';
import FAQSection from '@/components/landing/FAQSection';
import Footer from '@/components/landing/Footer';

export const metadata: Metadata = {
  title: 'RAG Transcript - AI-Powered Video Knowledge Base',
  description:
    'Transform YouTube videos into searchable knowledge with AI-powered transcription and semantic search. Chat with your videos and get precise, cited answers.',
};

/**
 * Home Page - Full SaaS landing page
 * No MainLayout (custom header + sections + footer)
 */
export default function HomePage() {
  return (
    <div className="min-h-screen bg-white">
      {/* Sticky navigation header */}
      <header className="border-b border-gray-200 bg-white/80 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            {/* Logo */}
            <a href="/" className="text-2xl font-bold text-primary">
              RAG Transcript
            </a>

            {/* Navigation */}
            <nav className="hidden md:flex items-center gap-8">
              <a
                href="#features"
                className="text-gray-600 hover:text-primary transition-colors"
              >
                Features
              </a>
              <a
                href="#pricing"
                className="text-gray-600 hover:text-primary transition-colors"
              >
                Pricing
              </a>
              <a
                href="#faq"
                className="text-gray-600 hover:text-primary transition-colors"
              >
                FAQ
              </a>
            </nav>

            {/* Auth buttons */}
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
      <main>
        <HeroSection />
        <div id="features">
          <FeaturesSection />
        </div>
        <PricingSection />
        <FAQSection />
      </main>

      {/* Footer */}
      <Footer />
    </div>
  );
}
