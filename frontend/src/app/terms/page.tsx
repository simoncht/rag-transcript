import React from 'react';
import type { Metadata } from 'next';
import Footer from '@/components/landing/Footer';

export const metadata: Metadata = {
  title: 'Terms of Service - RAG Transcript',
  description: 'Terms of Service for RAG Transcript - Read our terms and conditions for using the service.',
};

/**
 * Terms of Service Page
 * Public route (works without auth)
 */
export default function TermsPage() {
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
        <h1 className="text-4xl font-bold text-gray-900 mb-8">Terms of Service</h1>

        <div className="prose prose-lg max-w-none">
          <p className="text-gray-600 mb-6">
            Last updated: January 2026
          </p>

          <section className="mb-8">
            <h2 className="text-2xl font-semibold text-gray-900 mb-4">1. Acceptance of Terms</h2>
            <p className="text-gray-600">
              By accessing or using RAG Transcript, you agree to be bound by these Terms of Service.
              If you do not agree to these terms, please do not use our service.
            </p>
          </section>

          <section className="mb-8">
            <h2 className="text-2xl font-semibold text-gray-900 mb-4">2. Description of Service</h2>
            <p className="text-gray-600">
              RAG Transcript provides AI-powered transcription and semantic search services for YouTube videos.
              Our service allows you to transcribe videos, create searchable knowledge bases, and have
              AI-powered conversations about your video content.
            </p>
          </section>

          <section className="mb-8">
            <h2 className="text-2xl font-semibold text-gray-900 mb-4">3. User Accounts</h2>
            <p className="text-gray-600 mb-4">
              To use certain features of our service, you must create an account. You agree to:
            </p>
            <ul className="list-disc pl-6 text-gray-600 space-y-2">
              <li>Provide accurate and complete information</li>
              <li>Maintain the security of your account credentials</li>
              <li>Notify us immediately of any unauthorized access</li>
              <li>Accept responsibility for all activities under your account</li>
            </ul>
          </section>

          <section className="mb-8">
            <h2 className="text-2xl font-semibold text-gray-900 mb-4">4. Acceptable Use</h2>
            <p className="text-gray-600 mb-4">
              You agree not to:
            </p>
            <ul className="list-disc pl-6 text-gray-600 space-y-2">
              <li>Use the service for any illegal purpose</li>
              <li>Upload content that violates third-party rights</li>
              <li>Attempt to bypass any security measures</li>
              <li>Use the service to harass, abuse, or harm others</li>
              <li>Reverse engineer or attempt to extract source code</li>
            </ul>
          </section>

          <section className="mb-8">
            <h2 className="text-2xl font-semibold text-gray-900 mb-4">5. Content Ownership</h2>
            <p className="text-gray-600">
              You retain ownership of any content you upload or create using our service. By using
              our service, you grant us a limited license to process and store your content solely
              for the purpose of providing the service.
            </p>
          </section>

          <section className="mb-8">
            <h2 className="text-2xl font-semibold text-gray-900 mb-4">6. Subscription and Payments</h2>
            <p className="text-gray-600 mb-4">
              Paid subscriptions are billed in advance on a monthly or yearly basis. You may cancel
              your subscription at any time. Refunds are available within 14 days of purchase as
              outlined in our refund policy.
            </p>
          </section>

          <section className="mb-8">
            <h2 className="text-2xl font-semibold text-gray-900 mb-4">7. Limitation of Liability</h2>
            <p className="text-gray-600">
              To the maximum extent permitted by law, RAG Transcript shall not be liable for any
              indirect, incidental, special, consequential, or punitive damages arising from your
              use of the service.
            </p>
          </section>

          <section className="mb-8">
            <h2 className="text-2xl font-semibold text-gray-900 mb-4">8. Modifications to Terms</h2>
            <p className="text-gray-600">
              We reserve the right to modify these terms at any time. We will notify you of any
              changes by posting the new terms on this page. Your continued use of the service
              after such changes constitutes your acceptance of the new terms.
            </p>
          </section>

          <section className="mb-8">
            <h2 className="text-2xl font-semibold text-gray-900 mb-4">9. Termination</h2>
            <p className="text-gray-600">
              We may terminate or suspend your account at any time for any reason, including
              violation of these terms. Upon termination, your right to use the service will
              immediately cease.
            </p>
          </section>

          <section className="mb-8">
            <h2 className="text-2xl font-semibold text-gray-900 mb-4">10. Contact Us</h2>
            <p className="text-gray-600">
              If you have any questions about these Terms of Service, please contact us at{' '}
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
