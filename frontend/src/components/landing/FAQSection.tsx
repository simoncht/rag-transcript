'use client';

import React, { useState } from 'react';
import Card from '../shared/Card';

interface FAQItem {
  question: string;
  answer: string;
}

const faqs: FAQItem[] = [
  {
    question: "What's included in the free tier?",
    answer:
      'The free tier includes 2 videos, 50 messages per month, 1 GB storage, and 120 minutes of transcription. Perfect for trying out the platform and small projects.',
  },
  {
    question: 'Can I upgrade anytime?',
    answer:
      'Yes! You can upgrade to Pro or Enterprise anytime. Your quota increases immediately, and you only pay for the remaining time in the billing period.',
  },
  {
    question: 'What happens to my data if I cancel?',
    answer:
      'Your data remains accessible for 30 days after cancellation. You can export your transcripts and conversations anytime. After 30 days, data is permanently deleted.',
  },
  {
    question: 'Do you offer refunds?',
    answer:
      'Yes, we offer a 14-day money-back guarantee for all paid plans. If you\'re not satisfied, contact us for a full refund within 14 days of purchase.',
  },
  {
    question: 'Is my data secure?',
    answer:
      'Absolutely. All data is encrypted in transit and at rest. We use industry-standard security practices and never share your data with third parties. Your videos and transcripts are private.',
  },
  {
    question: 'Can I export my conversations?',
    answer:
      'Yes! You can export conversations as JSON or plain text. Transcripts can be downloaded with timestamps and speaker labels. All your data is portable.',
  },
  {
    question: 'What AI models do you use?',
    answer:
      'We use OpenAI Whisper for transcription, state-of-the-art embedding models for semantic search, and support multiple LLM providers (OpenAI, Anthropic, Ollama) for conversations.',
  },
];

/**
 * FAQSection - Accordion with common questions
 */
export default function FAQSection() {
  const [openIndex, setOpenIndex] = useState<number | null>(null);

  const toggleFAQ = (index: number) => {
    setOpenIndex(openIndex === index ? null : index);
  };

  return (
    <section id="faq" className="py-20 bg-gray-50">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Section header */}
        <div className="text-center mb-16">
          <h2 className="text-4xl font-bold text-gray-900 mb-4">
            Frequently Asked Questions
          </h2>
          <p className="text-xl text-gray-600">
            Got questions? We&apos;ve got answers.
          </p>
        </div>

        {/* FAQ accordion */}
        <div className="space-y-4">
          {faqs.map((faq, index) => (
            <Card key={index} className="!p-0 overflow-hidden" hoverable={false}>
              <button
                onClick={() => toggleFAQ(index)}
                className="w-full text-left p-6 flex items-center justify-between hover:bg-gray-50 transition-colors"
              >
                <span className="text-lg font-semibold text-gray-900">
                  {faq.question}
                </span>
                <svg
                  className={`w-6 h-6 text-gray-400 transition-transform ${
                    openIndex === index ? 'transform rotate-180' : ''
                  }`}
                  fill="none"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path d="M19 9l-7 7-7-7" />
                </svg>
              </button>

              {/* Answer */}
              <div
                className={`overflow-hidden transition-all duration-300 ${
                  openIndex === index ? 'max-h-96' : 'max-h-0'
                }`}
              >
                <div className="px-6 pb-6 text-gray-600">{faq.answer}</div>
              </div>
            </Card>
          ))}
        </div>

        {/* Additional help */}
        <div className="text-center mt-12">
          <p className="text-gray-600">
            Still have questions?{' '}
            <a
              href="mailto:support@example.com"
              className="text-primary hover:underline font-medium"
            >
              Contact support
            </a>
          </p>
        </div>
      </div>
    </section>
  );
}
