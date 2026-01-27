'use client';

import React, { useState } from 'react';
import Card from '../shared/Card';

type Category = 'processing' | 'retrieval' | 'conversations';

interface Feature {
  icon: React.ReactNode;
  title: string;
  description: string;
  badge?: 'NEW' | 'PRO';
}

interface FeatureCategory {
  id: Category;
  name: string;
  description: string;
  features: Feature[];
}

const categories: FeatureCategory[] = [
  {
    id: 'processing',
    name: 'Video Processing',
    description: 'Powerful ingestion and transcription capabilities',
    features: [
      {
        icon: (
          <svg className="w-7 h-7" fill="none" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" viewBox="0 0 24 24" stroke="currentColor">
            <path d="M7 4v16M17 4v16M3 8h4m10 0h4M3 12h18M3 16h4m10 0h4M4 20h16a1 1 0 001-1V5a1 1 0 00-1-1H4a1 1 0 00-1 1v14a1 1 0 001 1z" />
          </svg>
        ),
        title: 'YouTube Ingestion',
        description: 'Full metadata extraction including chapters, thumbnails, descriptions, and channel info.',
      },
      {
        icon: (
          <svg className="w-7 h-7" fill="none" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" viewBox="0 0 24 24" stroke="currentColor">
            <path d="M13 10V3L4 14h7v7l9-11h-7z" />
          </svg>
        ),
        title: 'Fast Caption Fallback',
        description: 'Use existing YouTube captions for instant processing (1-4 seconds) when available.',
        badge: 'NEW',
      },
      {
        icon: (
          <svg className="w-7 h-7" fill="none" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" viewBox="0 0 24 24" stroke="currentColor">
            <path d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
          </svg>
        ),
        title: 'Whisper Transcription',
        description: 'High-accuracy AI transcription with speaker labels, timestamps, and automatic punctuation.',
      },
      {
        icon: (
          <svg className="w-7 h-7" fill="none" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" viewBox="0 0 24 24" stroke="currentColor">
            <path d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
        ),
        title: 'Transcript Export',
        description: 'Download transcripts as .txt files with timestamps, perfect for reference or sharing.',
      },
    ],
  },
  {
    id: 'retrieval',
    name: 'Search & Retrieval',
    description: 'Advanced RAG pipeline for precise information retrieval',
    features: [
      {
        icon: (
          <svg className="w-7 h-7" fill="none" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" viewBox="0 0 24 24" stroke="currentColor">
            <path d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
          </svg>
        ),
        title: 'Video Collections',
        description: 'Group videos by topic, project, or course. Query across your entire collection and get answers that synthesize multiple sources.',
        badge: 'NEW',
      },
      {
        icon: (
          <svg className="w-7 h-7" fill="none" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" viewBox="0 0 24 24" stroke="currentColor">
            <path d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
          </svg>
        ),
        title: 'Query Expansion',
        description: 'Rephrases your question multiple ways to find answers your exact words might miss.',
        badge: 'NEW',
      },
      {
        icon: (
          <svg className="w-7 h-7" fill="none" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" viewBox="0 0 24 24" stroke="currentColor">
            <path d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
          </svg>
        ),
        title: 'Hybrid Search',
        description: 'Finds results whether you use the exact words from the video or just describe what you mean. Never miss relevant content.',
        badge: 'NEW',
      },
      {
        icon: (
          <svg className="w-7 h-7" fill="none" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" viewBox="0 0 24 24" stroke="currentColor">
            <path d="M3 4h13M3 8h9m-9 4h6m4 0l4-4m0 0l4 4m-4-4v12" />
          </svg>
        ),
        title: 'Smart Ranking',
        description: 'AI reads each result carefully to surface the most relevant answers first, not just the closest word matches.',
      },
      {
        icon: (
          <svg className="w-7 h-7" fill="none" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" viewBox="0 0 24 24" stroke="currentColor">
            <circle cx="12" cy="12" r="10" />
            <polyline points="12 6 12 12 16 14" />
          </svg>
        ),
        title: 'Timestamp Precision',
        description: 'Every result pinpoints the exact moment in the video. Jump directly to the relevant 30-second segment.',
      },
    ],
  },
  {
    id: 'conversations',
    name: 'AI Conversations',
    description: 'Intelligent chat with memory and citations',
    features: [
      {
        icon: (
          <svg className="w-7 h-7" fill="none" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" viewBox="0 0 24 24" stroke="currentColor">
            <path d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
        ),
        title: 'Inline Citations',
        description: 'Every claim linked to its source with clickable timestamp badges that jump to the exact moment.',
      },
      {
        icon: (
          <svg className="w-7 h-7" fill="none" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" viewBox="0 0 24 24" stroke="currentColor">
            <path d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
          </svg>
        ),
        title: 'Conversation Memory',
        description: 'Built for real research. Your conversation continues across sessions, so complex projects never lose momentum.',
        badge: 'NEW',
      },
      {
        icon: (
          <svg className="w-7 h-7" fill="none" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" viewBox="0 0 24 24" stroke="currentColor">
            <path d="M11 3.055A9.001 9.001 0 1020.945 13H11V3.055z" />
            <path d="M20.488 9H15V3.512A9.025 9.025 0 0120.488 9z" />
          </svg>
        ),
        title: 'Topic Insights',
        description: 'Visual topic graphs and conversation summaries help you understand patterns across sources.',
      },
      {
        icon: (
          <svg className="w-7 h-7" fill="none" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" viewBox="0 0 24 24" stroke="currentColor">
            <path d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
          </svg>
        ),
        title: 'Multiple AI Modes',
        description: 'Chat mode for quick answers, Reasoner mode for step-by-step analysis of complex questions.',
        badge: 'PRO',
      },
    ],
  },
];

export default function FeaturesSection() {
  const [activeCategory, setActiveCategory] = useState<Category>('processing');

  const currentCategory = categories.find((c) => c.id === activeCategory)!;

  return (
    <section id="features" className="py-20 bg-gray-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Section header */}
        <div className="text-center mb-12">
          <h2 className="text-4xl font-bold text-gray-900 mb-4">
            Everything You Need to Master Video Content
          </h2>
          <p className="text-xl text-gray-600 max-w-2xl mx-auto">
            Powerful features designed for researchers, students, and professionals
            who need to extract insights from video content.
          </p>
        </div>

        {/* Category tabs */}
        <div className="flex flex-wrap justify-center gap-2 mb-12">
          {categories.map((category) => (
            <button
              key={category.id}
              onClick={() => setActiveCategory(category.id)}
              className={`px-6 py-3 rounded-lg font-medium transition-all ${
                activeCategory === category.id
                  ? 'bg-primary text-white shadow-lg'
                  : 'bg-white text-gray-600 hover:bg-gray-100 border border-gray-200'
              }`}
            >
              {category.name}
            </button>
          ))}
        </div>

        {/* Category description */}
        <p className="text-center text-gray-500 mb-8 max-w-xl mx-auto">
          {currentCategory.description}
        </p>

        {/* Feature grid - 2x2 */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {currentCategory.features.map((feature, index) => (
            <Card key={index} className="relative">
              <div className="flex gap-4">
                {/* Icon */}
                <div className="flex-shrink-0 w-14 h-14 bg-primary/10 rounded-xl flex items-center justify-center text-primary">
                  {feature.icon}
                </div>

                {/* Content */}
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-2">
                    <h3 className="text-lg font-bold text-gray-900">
                      {feature.title}
                    </h3>
                    {feature.badge && (
                      <span
                        className={`px-2 py-0.5 text-xs font-bold rounded ${
                          feature.badge === 'NEW'
                            ? 'bg-green-100 text-green-700'
                            : 'bg-purple-100 text-purple-700'
                        }`}
                      >
                        {feature.badge}
                      </span>
                    )}
                  </div>
                  <p className="text-gray-600 text-sm leading-relaxed">
                    {feature.description}
                  </p>
                </div>
              </div>
            </Card>
          ))}
        </div>

        {/* View all features link */}
        <div className="text-center mt-10">
          <p className="text-gray-500">
            <span className="font-semibold text-gray-700">13 features</span> across 3 categories to supercharge your video research
          </p>
        </div>
      </div>
    </section>
  );
}
