'use client';

import React from 'react';
import { Lightbulb, GraduationCap, Video, Briefcase, ArrowRight } from 'lucide-react';

interface Testimonial {
  quote: string;
  author: string;
  role: string;
}

interface UseCase {
  id: string;
  title: string;
  persona: string;
  metric: string;
  description: string;
  testimonial: Testimonial;
  icon: React.ReactNode;
}

const useCases: UseCase[] = [
  {
    id: 'researchers',
    title: 'Researchers',
    persona: 'Academic & Market Research',
    metric: '10x faster',
    description: 'Stop rewatching hours of interview footage. Extract quotes with precise citations in minutes.',
    testimonial: {
      quote: "I processed 50 interviews in 2 days instead of 2 weeks.",
      author: "Dr. Sarah Chen",
      role: "Stanford University"
    },
    icon: <Lightbulb className="w-6 h-6" />
  },
  {
    id: 'students',
    title: 'Students',
    persona: 'Education & Learning',
    metric: 'Instant answers',
    description: 'Turn lecture recordings into searchable study notes. Find explanations instantly before exams.',
    testimonial: {
      quote: "Found the exact explanation I needed in a 2-hour lecture in 10 seconds.",
      author: "Alex Rivera",
      role: "MIT Student"
    },
    icon: <GraduationCap className="w-6 h-6" />
  },
  {
    id: 'creators',
    title: 'Content Creators',
    persona: 'Video & Podcast Production',
    metric: '1 video → 10+ posts',
    description: 'Repurpose long-form content into blogs, social posts, and clips without rewatching.',
    testimonial: {
      quote: "I create a week of content from one podcast episode now.",
      author: "Marcus Johnson",
      role: "YouTuber, 500K subs"
    },
    icon: <Video className="w-6 h-6" />
  },
  {
    id: 'professionals',
    title: 'Professionals',
    persona: 'Training & Knowledge Management',
    metric: '100+ hours searchable',
    description: 'Build searchable libraries from training videos, webinars, and recorded meetings.',
    testimonial: {
      quote: "New hires find answers themselves instead of asking the same questions.",
      author: "Jennifer Park",
      role: "L&D Director, Fortune 500"
    },
    icon: <Briefcase className="w-6 h-6" />
  }
];

export default function UseCasesSection() {
  const handleGetStarted = () => {
    window.location.href = '/login';
  };

  const handleSeePricing = () => {
    document.getElementById('pricing')?.scrollIntoView({ behavior: 'smooth' });
  };

  return (
    <section id="use-cases" className="py-20 bg-[var(--color-bg-secondary)]">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Section header */}
        <div className="text-center mb-12">
          <h2 className="text-4xl font-bold text-[var(--color-text-primary)] mb-4">
            Built for How You Work
          </h2>
          <p className="text-xl text-[var(--color-text-secondary)] max-w-2xl mx-auto">
            Whether you&apos;re researching, learning, creating, or training —
            unlock the knowledge trapped in your video content.
          </p>
        </div>

        {/* Bento grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {/* Featured card - Researchers */}
          <div className="lg:row-span-2 bg-white border border-[var(--color-border)] rounded-2xl overflow-hidden hover:shadow-lg hover:border-[var(--color-border-dark)] transition-all duration-300 flex flex-col">
            {/* Top accent stripe */}
            <div className="h-1 bg-gradient-to-r from-[var(--color-primary)] to-[var(--color-primary-dark)]" />

            <div className="p-6 flex flex-col flex-1">
              {/* Header */}
              <div className="flex items-center gap-3 mb-4">
                <div className="w-11 h-11 bg-[var(--color-primary)]/10 rounded-xl flex items-center justify-center text-[var(--color-primary)]">
                  {useCases[0].icon}
                </div>
                <div>
                  <h3 className="text-lg font-bold text-[var(--color-text-primary)]">{useCases[0].title}</h3>
                  <p className="text-sm text-[var(--color-text-secondary)]">{useCases[0].persona}</p>
                </div>
              </div>

              {/* Metric */}
              <div className="inline-flex w-fit px-3 py-1 bg-[var(--color-primary)]/10 text-[var(--color-primary-dark)] text-sm font-semibold rounded-full mb-4">
                {useCases[0].metric}
              </div>

              {/* Description */}
              <p className="text-[var(--color-text-secondary)] mb-6 leading-relaxed">{useCases[0].description}</p>

              {/* Testimonial */}
              <div className="mt-auto pt-5 border-t border-[var(--color-border)]">
                <blockquote className="text-[var(--color-text-secondary)] italic">
                  &ldquo;{useCases[0].testimonial.quote}&rdquo;
                </blockquote>
                <cite className="block mt-2 text-sm text-[var(--color-text-tertiary)] not-italic">
                  — {useCases[0].testimonial.author}, {useCases[0].testimonial.role}
                </cite>
              </div>
            </div>
          </div>

          {/* Standard cards */}
          {useCases.slice(1).map((useCase) => (
            <div
              key={useCase.id}
              className="bg-white border border-[var(--color-border)] rounded-2xl overflow-hidden hover:shadow-lg hover:border-[var(--color-border-dark)] transition-all duration-300"
            >
              {/* Top accent stripe */}
              <div className="h-1 bg-gradient-to-r from-[var(--color-primary)] to-[var(--color-primary-dark)]" />

              <div className="p-5">
                {/* Header */}
                <div className="flex items-center gap-3 mb-3">
                  <div className="w-10 h-10 bg-[var(--color-primary)]/10 rounded-xl flex items-center justify-center text-[var(--color-primary)]">
                    {useCase.icon}
                  </div>
                  <div>
                    <h3 className="text-lg font-bold text-[var(--color-text-primary)]">{useCase.title}</h3>
                    <p className="text-sm text-[var(--color-text-secondary)]">{useCase.persona}</p>
                  </div>
                </div>

                {/* Metric */}
                <div className="inline-flex px-3 py-1 bg-[var(--color-primary)]/10 text-[var(--color-primary-dark)] text-sm font-semibold rounded-full mb-3">
                  {useCase.metric}
                </div>

                {/* Description */}
                <p className="text-[var(--color-text-secondary)] text-sm mb-4 leading-relaxed">{useCase.description}</p>

                {/* Compact testimonial */}
                <div className="pt-4 border-t border-[var(--color-border)]">
                  <p className="text-sm text-[var(--color-text-tertiary)] italic">
                    &ldquo;{useCase.testimonial.quote}&rdquo;
                  </p>
                  <p className="text-xs text-[var(--color-text-tertiary)] mt-1">
                    — {useCase.testimonial.author}
                  </p>
                </div>
              </div>
            </div>
          ))}

          {/* CTA Card */}
          <div className="bg-white border border-[var(--color-border)] rounded-2xl overflow-hidden hover:shadow-lg hover:border-[var(--color-border-dark)] transition-all duration-300">
            {/* Top accent stripe - uses accent color */}
            <div className="h-1 bg-gradient-to-r from-[var(--color-accent)] to-[var(--color-accent-dark)]" />

            <div className="p-6 flex flex-col justify-center items-center text-center h-full">
              <h3 className="text-xl font-bold text-[var(--color-text-primary)] mb-2">Which one are you?</h3>
              <p className="text-[var(--color-text-secondary)] text-sm mb-5">
                Start transforming your video workflow today.
              </p>
              <div className="flex flex-col gap-3 w-full max-w-xs">
                <button
                  onClick={handleGetStarted}
                  className="w-full px-5 py-2.5 bg-[var(--color-primary)] text-white font-medium rounded-xl hover:bg-[var(--color-primary-dark)] transition-colors duration-200 flex items-center justify-center gap-2 group"
                >
                  Get Started Free
                  <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
                </button>
                <button
                  onClick={handleSeePricing}
                  className="w-full px-5 py-2.5 border border-[var(--color-border)] text-[var(--color-text-primary)] font-medium rounded-xl hover:bg-[var(--color-bg-secondary)] transition-colors duration-200"
                >
                  See Pricing
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
