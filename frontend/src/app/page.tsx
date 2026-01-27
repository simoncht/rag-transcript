import React from 'react';
import type { Metadata } from 'next';
import HeroSection from '@/components/landing/HeroSection';
import HowItWorksSection from '@/components/landing/HowItWorksSection';
import FeaturesSection from '@/components/landing/FeaturesSection';
import TechnologySection from '@/components/landing/TechnologySection';
import UseCasesSection from '@/components/landing/UseCasesSection';
import ComparisonSection from '@/components/landing/ComparisonSection';
import TestimonialsSection from '@/components/landing/TestimonialsSection';
import PricingSection from '@/components/landing/PricingSection';
import FAQSection from '@/components/landing/FAQSection';
import FinalCTASection from '@/components/landing/FinalCTASection';
import Footer from '@/components/landing/Footer';
import HeaderAuthButtons from '@/components/landing/HeaderAuthButtons';

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
            <nav className="hidden md:flex items-center gap-6">
              <a
                href="#how-it-works"
                className="text-gray-600 hover:text-primary transition-colors text-sm"
              >
                How It Works
              </a>
              <a
                href="#features"
                className="text-gray-600 hover:text-primary transition-colors text-sm"
              >
                Features
              </a>
              <a
                href="#technology"
                className="text-gray-600 hover:text-primary transition-colors text-sm"
              >
                Technology
              </a>
              <a
                href="#use-cases"
                className="text-gray-600 hover:text-primary transition-colors text-sm"
              >
                Use Cases
              </a>
              <a
                href="#pricing"
                className="text-gray-600 hover:text-primary transition-colors text-sm"
              >
                Pricing
              </a>
              <a
                href="#faq"
                className="text-gray-600 hover:text-primary transition-colors text-sm"
              >
                FAQ
              </a>
            </nav>

            {/* Auth buttons */}
            <HeaderAuthButtons />
          </div>
        </div>
      </header>

      {/* Main content */}
      <main>
        <HeroSection />
        <HowItWorksSection />
        <FeaturesSection />
        <TechnologySection />
        <UseCasesSection />
        <ComparisonSection />
        <TestimonialsSection />
        <PricingSection />
        <FAQSection />
        <FinalCTASection />
      </main>

      {/* Footer */}
      <Footer />
    </div>
  );
}
