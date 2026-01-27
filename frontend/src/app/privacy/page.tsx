import React from 'react';
import type { Metadata } from 'next';
import Footer from '@/components/landing/Footer';

export const metadata: Metadata = {
  title: 'Privacy Policy - RAG Transcript',
  description: 'Privacy Policy for RAG Transcript - Learn how we collect, use, and protect your data.',
};

/**
 * Privacy Policy Page
 * Public route (works without auth)
 */
export default function PrivacyPage() {
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
      <main className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
        <h1 className="text-4xl font-bold text-gray-900 mb-8">Privacy Policy</h1>

        <div className="prose prose-lg max-w-none">
          <p className="text-gray-600 mb-6">
            Last updated: January 2026
          </p>

          <section className="mb-8">
            <h2 className="text-2xl font-semibold text-gray-900 mb-4">1. Information We Collect</h2>
            <p className="text-gray-600 mb-4">
              We collect information you provide directly to us, including:
            </p>
            <ul className="list-disc pl-6 text-gray-600 space-y-2">
              <li>Account information (email address, name) when you sign up</li>
              <li>YouTube video URLs you submit for transcription</li>
              <li>Conversations and messages you create within the platform</li>
              <li>Usage data and analytics to improve our service</li>
            </ul>
          </section>

          <section className="mb-8">
            <h2 className="text-2xl font-semibold text-gray-900 mb-4">2. How We Use Your Information</h2>
            <p className="text-gray-600 mb-4">
              We use the information we collect to:
            </p>
            <ul className="list-disc pl-6 text-gray-600 space-y-2">
              <li>Provide, maintain, and improve our services</li>
              <li>Process and complete your transcription requests</li>
              <li>Send you technical notices and support messages</li>
              <li>Respond to your comments and questions</li>
            </ul>
          </section>

          <section className="mb-8">
            <h2 className="text-2xl font-semibold text-gray-900 mb-4">3. Data Security</h2>
            <p className="text-gray-600">
              We take reasonable measures to help protect your personal information from loss, theft, misuse,
              unauthorized access, disclosure, alteration, and destruction. All data is encrypted in transit
              and at rest using industry-standard encryption protocols.
            </p>
          </section>

          <section className="mb-8">
            <h2 className="text-2xl font-semibold text-gray-900 mb-4">4. Data Retention</h2>
            <p className="text-gray-600">
              We retain your data for as long as your account is active or as needed to provide you services.
              If you delete your account, we will delete your data within 30 days, except where we are required
              to retain it for legal purposes.
            </p>
          </section>

          <section className="mb-8">
            <h2 className="text-2xl font-semibold text-gray-900 mb-4">5. Third-Party Services</h2>
            <p className="text-gray-600">
              We use third-party services for authentication (Clerk), payment processing (Stripe), and
              AI services (OpenAI, Anthropic). These services have their own privacy policies governing
              their use of your information.
            </p>
          </section>

          <section className="mb-8">
            <h2 className="text-2xl font-semibold text-gray-900 mb-4">6. Your Rights</h2>
            <p className="text-gray-600 mb-4">
              You have the right to:
            </p>
            <ul className="list-disc pl-6 text-gray-600 space-y-2">
              <li>Access your personal data</li>
              <li>Correct inaccurate data</li>
              <li>Request deletion of your data</li>
              <li>Export your data in a portable format</li>
            </ul>
          </section>

          <section className="mb-8">
            <h2 className="text-2xl font-semibold text-gray-900 mb-4">7. Contact Us</h2>
            <p className="text-gray-600">
              If you have any questions about this Privacy Policy, please contact us at{' '}
              <a href="mailto:support@ragtranscript.com" className="text-primary hover:underline">
                support@ragtranscript.com
              </a>
            </p>
          </section>
        </div>
      </main>

      <Footer />
    </div>
  );
}
