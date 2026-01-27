'use client';

import React from 'react';

interface ComparisonRow {
  feature: string;
  ragTranscript: string | boolean;
  others: string | boolean;
  highlight?: boolean;
}

const comparisons: ComparisonRow[] = [
  {
    feature: 'Semantic search',
    ragTranscript: true,
    others: 'Keyword only',
    highlight: true,
  },
  {
    feature: 'Inline citations with timestamps',
    ragTranscript: true,
    others: false,
    highlight: true,
  },
  {
    feature: 'Jump-to-timestamp links',
    ragTranscript: true,
    others: 'Rare',
  },
  {
    feature: 'Conversation memory',
    ragTranscript: true,
    others: false,
    highlight: true,
  },
  {
    feature: 'Query expansion (multi-query)',
    ragTranscript: true,
    others: false,
  },
  {
    feature: 'Cross-encoder reranking',
    ragTranscript: true,
    others: false,
  },
  {
    feature: 'Response time',
    ragTranscript: '~4 seconds',
    others: '10-30 seconds',
    highlight: true,
  },
  {
    feature: 'Context window',
    ragTranscript: '128K tokens',
    others: '4K-32K',
  },
];

const CheckIcon = () => (
  <svg className="w-5 h-5 text-green-600" fill="currentColor" viewBox="0 0 20 20">
    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
  </svg>
);

const XIcon = () => (
  <svg className="w-5 h-5 text-gray-400" fill="currentColor" viewBox="0 0 20 20">
    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
  </svg>
);

export default function ComparisonSection() {
  return (
    <section className="py-20 bg-white">
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Section header */}
        <div className="text-center mb-12">
          <h2 className="text-4xl font-bold text-gray-900 mb-4">
            How We Compare
          </h2>
          <p className="text-xl text-gray-600 max-w-2xl mx-auto">
            Purpose-built for video knowledge extraction, not a generic transcription tool.
          </p>
        </div>

        {/* Comparison table */}
        <div className="bg-white rounded-2xl shadow-lg border border-gray-200 overflow-hidden">
          {/* Table header */}
          <div className="grid grid-cols-3 bg-gray-50 border-b border-gray-200">
            <div className="p-4 font-semibold text-gray-600">Feature</div>
            <div className="p-4 font-bold text-primary text-center border-l border-gray-200 bg-primary/5">
              RAG Transcript
            </div>
            <div className="p-4 font-semibold text-gray-500 text-center border-l border-gray-200">
              Others
            </div>
          </div>

          {/* Table rows */}
          {comparisons.map((row, index) => (
            <div
              key={index}
              className={`grid grid-cols-3 border-b border-gray-100 last:border-0 ${
                row.highlight ? 'bg-green-50/50' : ''
              }`}
            >
              <div className={`p-4 text-gray-700 ${row.highlight ? 'font-medium' : ''}`}>
                {row.feature}
              </div>
              <div className="p-4 flex items-center justify-center border-l border-gray-100 bg-primary/5">
                {typeof row.ragTranscript === 'boolean' ? (
                  row.ragTranscript ? <CheckIcon /> : <XIcon />
                ) : (
                  <span className="text-green-700 font-medium">{row.ragTranscript}</span>
                )}
              </div>
              <div className="p-4 flex items-center justify-center border-l border-gray-100">
                {typeof row.others === 'boolean' ? (
                  row.others ? <CheckIcon /> : <XIcon />
                ) : (
                  <span className="text-gray-500">{row.others}</span>
                )}
              </div>
            </div>
          ))}
        </div>

        {/* Summary */}
        <p className="text-center text-gray-500 mt-8 text-sm">
          Comparison based on publicly available features of common video transcription and AI chat tools.
        </p>
      </div>
    </section>
  );
}
