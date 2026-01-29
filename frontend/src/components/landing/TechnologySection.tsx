'use client';

import React from 'react';
import Card from '../shared/Card';

interface Metric {
  value: string;
  label: string;
  description: string;
}

const metrics: Metric[] = [
  {
    value: 'Multi-Video',
    label: 'Synthesis',
    description: 'Answers that connect insights across your library',
  },
  {
    value: 'Nothing',
    label: 'Missed',
    description: 'Every piece of your content becomes searchable',
  },
  {
    value: '100%',
    label: 'Cited Answers',
    description: 'Every response links to the source',
  },
  {
    value: 'Exact',
    label: 'Moment',
    description: 'Jump to the precise second, every time',
  },
];

export default function TechnologySection() {
  return (
    <section id="technology" className="py-20 bg-gradient-to-b from-orange-50 to-white">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Section header */}
        <div className="text-center mb-16">
          <h2 className="text-4xl font-bold text-gray-900 mb-4">
            Why It Works So Well
          </h2>
          <p className="text-xl text-gray-600 max-w-2xl mx-auto">
            Advanced AI that actually understands your videos—not just keywords.
          </p>
        </div>

        {/* Performance metrics */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-16">
          {metrics.map((metric, index) => (
            <Card key={index} className="text-center">
              <div className="text-3xl font-bold text-primary mb-1">
                {metric.value}
              </div>
              <div className="text-sm font-semibold text-gray-900 mb-1">
                {metric.label}
              </div>
              <div className="text-xs text-gray-500">
                {metric.description}
              </div>
            </Card>
          ))}
        </div>

        {/* AI Models comparison - Simplified for users */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <Card>
            <div className="flex items-start gap-4">
              <div className="w-12 h-12 bg-blue-100 rounded-xl flex items-center justify-center flex-shrink-0">
                <svg className="w-6 h-6 text-blue-600" fill="none" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" viewBox="0 0 24 24" stroke="currentColor">
                  <path d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
              </div>
              <div>
                <h4 className="text-lg font-bold text-gray-900 mb-2">
                  Quick Mode
                </h4>
                <p className="text-gray-600 text-sm mb-3">
                  Fast answers for simple questions. Perfect for quick lookups and fact checks.
                </p>
                <div className="flex items-center gap-2 text-sm">
                  <span className="px-2 py-1 bg-green-100 text-green-700 rounded font-medium">Fast</span>
                  <span className="px-2 py-1 bg-blue-100 text-blue-700 rounded font-medium">Simple</span>
                </div>
              </div>
            </div>
          </Card>

          <Card>
            <div className="flex items-start gap-4">
              <div className="w-12 h-12 bg-purple-100 rounded-xl flex items-center justify-center flex-shrink-0">
                <svg className="w-6 h-6 text-purple-600" fill="none" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" viewBox="0 0 24 24" stroke="currentColor">
                  <path d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                </svg>
              </div>
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <h4 className="text-lg font-bold text-gray-900">
                    Deep Analysis Mode
                  </h4>
                  <span className="px-2 py-0.5 text-xs font-bold bg-purple-100 text-purple-700 rounded">
                    PRO
                  </span>
                </div>
                <p className="text-gray-600 text-sm mb-3">
                  Thoughtful analysis for complex questions. Connects ideas across your entire video library.
                </p>
                <div className="flex items-center gap-2 text-sm">
                  <span className="px-2 py-1 bg-purple-100 text-purple-700 rounded font-medium">Thorough</span>
                  <span className="px-2 py-1 bg-indigo-100 text-indigo-700 rounded font-medium">Insightful</span>
                </div>
              </div>
            </div>
          </Card>
        </div>

        {/* Conversation Memory */}
        <Card className="mt-8">
          <div className="flex flex-col md:flex-row items-start gap-6">
            <div className="w-16 h-16 bg-green-100 rounded-xl flex items-center justify-center flex-shrink-0">
              <svg className="w-8 h-8 text-green-600" fill="none" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" viewBox="0 0 24 24" stroke="currentColor">
                <path d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
              </svg>
            </div>
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-2">
                <h4 className="text-lg font-bold text-gray-900">
                  Persistent Conversation Memory
                </h4>
                <span className="px-2 py-0.5 text-xs font-bold bg-green-100 text-green-700 rounded">
                  NEW
                </span>
              </div>
              <p className="text-gray-600 mb-4">
                Your full conversation is saved—and our AI learns what matters. Key facts are extracted from every exchange, so even when the conversation grows long, important details from earlier aren&apos;t forgotten.
              </p>
              <div className="flex flex-wrap gap-4 text-sm">
                <div className="flex items-center gap-2">
                  <svg className="w-5 h-5 text-green-600" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                  </svg>
                  <span className="text-gray-700">Full history saved</span>
                </div>
                <div className="flex items-center gap-2">
                  <svg className="w-5 h-5 text-green-600" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                  </svg>
                  <span className="text-gray-700">Key facts extracted every turn</span>
                </div>
                <div className="flex items-center gap-2">
                  <svg className="w-5 h-5 text-green-600" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                  </svg>
                  <span className="text-gray-700">Long conversations stay coherent</span>
                </div>
              </div>
            </div>
          </div>
        </Card>
      </div>
    </section>
  );
}
