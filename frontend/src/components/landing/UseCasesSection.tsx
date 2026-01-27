'use client';

import React from 'react';
import Card from '../shared/Card';

interface UseCase {
  icon: React.ReactNode;
  title: string;
  persona: string;
  description: string;
  examples: string[];
}

const useCases: UseCase[] = [
  {
    icon: (
      <svg className="w-8 h-8" fill="none" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" viewBox="0 0 24 24" stroke="currentColor">
        <path d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
      </svg>
    ),
    title: 'Researchers',
    persona: 'Academic & Market Research',
    description: 'Analyze hours of interview footage in minutes. Extract quotes with precise citations for papers and reports.',
    examples: ['Qualitative interview analysis', 'Conference talk reviews', 'Literature video synthesis'],
  },
  {
    icon: (
      <svg className="w-8 h-8" fill="none" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" viewBox="0 0 24 24" stroke="currentColor">
        <path d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
      </svg>
    ),
    title: 'Students',
    persona: 'Education & Learning',
    description: 'Turn lecture recordings into searchable study notes. Find specific explanations instantly before exams.',
    examples: ['Lecture review and study', 'Tutorial video indexing', 'Exam prep from recordings'],
  },
  {
    icon: (
      <svg className="w-8 h-8" fill="none" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" viewBox="0 0 24 24" stroke="currentColor">
        <path d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
      </svg>
    ),
    title: 'Content Creators',
    persona: 'Video & Podcast Production',
    description: 'Repurpose long-form video into blogs, social posts, and clips. Find the best moments without rewatching.',
    examples: ['Podcast episode mining', 'Video-to-blog conversion', 'Clip identification'],
  },
  {
    icon: (
      <svg className="w-8 h-8" fill="none" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" viewBox="0 0 24 24" stroke="currentColor">
        <path d="M21 13.255A23.931 23.931 0 0112 15c-3.183 0-6.22-.62-9-1.745M16 6V4a2 2 0 00-2-2h-4a2 2 0 00-2 2v2m4 6h.01M5 20h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
      </svg>
    ),
    title: 'Professionals',
    persona: 'Training & Knowledge Management',
    description: 'Build searchable libraries from training videos, webinars, and recorded meetings.',
    examples: ['Onboarding video libraries', 'Meeting recording search', 'Training content indexing'],
  },
];

export default function UseCasesSection() {
  return (
    <section id="use-cases" className="py-20 bg-white">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Section header */}
        <div className="text-center mb-16">
          <h2 className="text-4xl font-bold text-gray-900 mb-4">
            Built for How You Work
          </h2>
          <p className="text-xl text-gray-600 max-w-2xl mx-auto">
            Whether you&apos;re researching, learning, creating, or training - unlock the knowledge trapped in video content.
          </p>
        </div>

        {/* Use case grid - 2x2 */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          {useCases.map((useCase, index) => (
            <Card key={index} className="h-full">
              <div className="flex flex-col h-full">
                {/* Header */}
                <div className="flex items-center gap-4 mb-4">
                  <div className="w-14 h-14 bg-primary/10 rounded-xl flex items-center justify-center text-primary">
                    {useCase.icon}
                  </div>
                  <div>
                    <h3 className="text-xl font-bold text-gray-900">
                      {useCase.title}
                    </h3>
                    <p className="text-sm text-primary font-medium">
                      {useCase.persona}
                    </p>
                  </div>
                </div>

                {/* Description */}
                <p className="text-gray-600 mb-4 flex-grow">
                  {useCase.description}
                </p>

                {/* Example use cases */}
                <div className="pt-4 border-t border-gray-100">
                  <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
                    Example uses
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {useCase.examples.map((example, i) => (
                      <span
                        key={i}
                        className="px-3 py-1 bg-gray-100 text-gray-600 text-sm rounded-full"
                      >
                        {example}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            </Card>
          ))}
        </div>
      </div>
    </section>
  );
}
