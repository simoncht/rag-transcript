'use client';

import React from 'react';
import Card from '../shared/Card';

interface Feature {
  icon: React.ReactNode;
  title: string;
  description: string;
}

const features: Feature[] = [
  {
    icon: (
      <svg
        className="w-8 h-8 text-primary"
        fill="none"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="2"
        viewBox="0 0 24 24"
        stroke="currentColor"
      >
        <path d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
      </svg>
    ),
    title: 'AI-Powered Transcription',
    description:
      'Automatic transcription with Whisper AI. Speaker labels, timestamps, and chapter detection for accurate, searchable transcripts.',
  },
  {
    icon: (
      <svg
        className="w-8 h-8 text-primary"
        fill="none"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="2"
        viewBox="0 0 24 24"
        stroke="currentColor"
      >
        <path d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
      </svg>
    ),
    title: 'Semantic Search with Citations',
    description:
      'Find information using natural language. Every answer includes precise citations with video timestamps and jump URLs.',
  },
  {
    icon: (
      <svg
        className="w-8 h-8 text-primary"
        fill="none"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="2"
        viewBox="0 0 24 24"
        stroke="currentColor"
      >
        <path d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
      </svg>
    ),
    title: 'Conversation Memory',
    description:
      'Multi-turn conversations that remember context. The AI extracts and retains key facts for coherent, context-aware responses.',
  },
  {
    icon: (
      <svg
        className="w-8 h-8 text-primary"
        fill="none"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="2"
        viewBox="0 0 24 24"
        stroke="currentColor"
      >
        <path d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
      </svg>
    ),
    title: 'Collection Management',
    description:
      'Organize videos into collections. Course materials, project resources, or knowledge bases - keep everything structured.',
  },
];

/**
 * FeaturesSection - 4 feature cards with icons
 * Grid layout (2x2 on lg, 1 col on mobile)
 */
export default function FeaturesSection() {
  return (
    <section className="py-20 bg-gray-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Section header */}
        <div className="text-center mb-16">
          <h2 className="text-4xl font-bold text-gray-900 mb-4">
            Everything You Need to Master Video Content
          </h2>
          <p className="text-xl text-gray-600 max-w-2xl mx-auto">
            Powerful features designed for researchers, students, and professionals
            who need to extract insights from video content.
          </p>
        </div>

        {/* Feature grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          {features.map((feature, index) => (
            <Card key={index} className="text-center">
              <div className="flex flex-col items-center">
                <div className="mb-4">{feature.icon}</div>
                <h3 className="text-xl font-bold text-gray-900 mb-3">
                  {feature.title}
                </h3>
                <p className="text-gray-600">{feature.description}</p>
              </div>
            </Card>
          ))}
        </div>
      </div>
    </section>
  );
}
