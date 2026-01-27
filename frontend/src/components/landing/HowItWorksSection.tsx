'use client';

import React, { useEffect, useRef, useState } from 'react';

interface Step {
  number: number;
  icon: React.ReactNode;
  title: string;
  description: string;
  timeBadge: string;
}

// Clock icon for time badges
const ClockIcon = ({ className = "w-3.5 h-3.5" }: { className?: string }) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="10" />
    <polyline points="12 6 12 12 16 14" />
  </svg>
);

// Clean icons that inherit stroke color
const LinkIcon = () => (
  <svg className="w-7 h-7" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
    <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
    <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
  </svg>
);

const WaveformIcon = () => (
  <svg className="w-7 h-7" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
    <path d="M2 10v4" />
    <path d="M6 6v12" />
    <path d="M10 8v8" />
    <path d="M14 4v16" />
    <path d="M18 8v8" />
    <path d="M22 10v4" />
  </svg>
);

const BrainSparkleIcon = () => (
  <svg className="w-7 h-7" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 5a3 3 0 1 0-5.997.125 4 4 0 0 0-2.526 5.77 4 4 0 0 0 .556 6.588A4 4 0 1 0 12 18Z" />
    <path d="M12 5a3 3 0 1 1 5.997.125 4 4 0 0 1 2.526 5.77 4 4 0 0 1-.556 6.588A4 4 0 1 1 12 18Z" />
    <path d="M15 13a4.5 4.5 0 0 1-3-4 4.5 4.5 0 0 1-3 4" />
    <path d="M12 18v4" />
  </svg>
);

const ChatBubblesIcon = () => (
  <svg className="w-7 h-7" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
    <path d="M7.9 20A9 9 0 1 0 4 16.1L2 22Z" />
    <path d="M8 12h.01" />
    <path d="M12 12h.01" />
    <path d="M16 12h.01" />
  </svg>
);

// Simple chevron connector between cards
const ChevronConnector = ({ isVisible, delay }: { isVisible: boolean; delay: number }) => (
  <div
    className={`hidden lg:flex items-center justify-center w-8 self-center -mx-1 ${
      isVisible ? 'animate-fade-in-up' : 'opacity-0'
    }`}
    style={{ animationDelay: `${delay}ms` }}
  >
    <svg
      viewBox="0 0 24 24"
      className="w-6 h-6 text-[var(--color-primary)]"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M9 18l6-6-6-6" />
    </svg>
  </div>
);

const steps: Step[] = [
  {
    number: 1,
    icon: <LinkIcon />,
    title: 'Drop a Link',
    description: 'Paste any YouTube URL. We handle the rest in seconds.',
    timeBadge: '~10 seconds',
  },
  {
    number: 2,
    icon: <WaveformIcon />,
    title: 'Instant Transcription',
    description: 'AI converts speech to text with 95%+ accuracy. Timestamps included.',
    timeBadge: '1-3 minutes',
  },
  {
    number: 3,
    icon: <BrainSparkleIcon />,
    title: 'Deep Understanding',
    description: 'Content is analyzed, enriched, and made searchable by meaning.',
    timeBadge: 'Automatic',
  },
  {
    number: 4,
    icon: <ChatBubblesIcon />,
    title: 'Ask Anything',
    description: 'Get precise answers with clickable citations. Jump to the exact moment.',
    timeBadge: 'Instant',
  },
];


// Desktop step card component
const StepCard = ({
  step,
  index,
  isVisible,
}: {
  step: Step;
  index: number;
  isVisible: boolean;
}) => {
  const delays = [0, 150, 300, 450];
  const animationDelay = delays[index];

  return (
    <div
      className={`relative group flex flex-col ${
        isVisible ? 'animate-fade-in-up' : 'opacity-0'
      }`}
      style={{ animationDelay: `${animationDelay}ms` }}
    >
      {/* Step number badge - terracotta, centered at top */}
      <div className="absolute -top-5 left-1/2 -translate-x-1/2 z-20 w-10 h-10 rounded-full bg-gradient-to-br from-[var(--color-accent)] to-[var(--color-accent-dark)] flex items-center justify-center text-white font-bold text-base shadow-lg ring-4 ring-white">
        {step.number}
      </div>

      {/* Card - fixed height for consistency */}
      <div className="bg-white rounded-2xl shadow-lg overflow-hidden transition-all duration-300 hover:-translate-y-2 hover:shadow-xl border border-[var(--color-border)]/50 w-56 h-[320px] flex flex-col">
        {/* Top gradient stripe - sage green */}
        <div className="h-2 bg-gradient-to-r from-[var(--color-primary)] to-[var(--color-primary-dark)] flex-shrink-0" />

        {/* Content */}
        <div className="p-6 pt-8 text-center flex flex-col flex-1">
          {/* Icon - simple square with rounded corners */}
          <div
            className={`w-14 h-14 mx-auto mb-5 rounded-xl bg-[var(--color-primary)]/10 flex items-center justify-center flex-shrink-0 border border-[var(--color-primary)]/20 text-[var(--color-primary)] ${
              isVisible ? 'animate-float' : ''
            }`}
            style={{ animationDelay: `${index * 400}ms` }}
          >
            {step.icon}
          </div>

          {/* Title - fixed height for 2 lines */}
          <h3 className="text-lg font-semibold text-[var(--color-text-primary)] mb-2 min-h-[3.5rem] flex items-center justify-center">
            {step.title}
          </h3>

          {/* Time badge - warm tan */}
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-[var(--color-secondary-light)]/30 text-[var(--color-secondary-dark)] text-sm font-medium mb-3 mx-auto flex-shrink-0">
            <ClockIcon className="w-3.5 h-3.5" />
            {step.timeBadge}
          </span>

          {/* Description - flex grow to push content up */}
          <p className="text-sm text-[var(--color-text-secondary)] leading-relaxed flex-1">
            {step.description}
          </p>
        </div>
      </div>
    </div>
  );
};

// Mobile step card component
const MobileStepCard = ({
  step,
  index,
  isVisible,
  isLast,
}: {
  step: Step;
  index: number;
  isVisible: boolean;
  isLast: boolean;
}) => {
  const animationDelay = index * 150;

  return (
    <div className="relative">
      {/* Vertical connecting line with pulsing dot */}
      {!isLast && (
        <div className="absolute left-[2.25rem] top-[5.5rem] flex flex-col items-center">
          <div className="w-0.5 h-8 bg-gradient-to-b from-[var(--color-primary)] to-[var(--color-accent)]" />
          <div className="w-2 h-2 rounded-full bg-[var(--color-accent)] animate-pulse" />
          <div className="w-0.5 h-8 bg-gradient-to-b from-[var(--color-accent)] to-[var(--color-primary)]/30" />
        </div>
      )}

      <div
        className={`${isVisible ? 'animate-fade-in-up' : 'opacity-0'}`}
        style={{ animationDelay: `${animationDelay}ms` }}
      >
        {/* Step badge above card */}
        <div className="flex items-center gap-2 mb-3">
          <div className="w-7 h-7 rounded-full bg-[var(--color-accent)] flex items-center justify-center text-white font-bold text-sm shadow-md">
            {step.number}
          </div>
          <span className="text-sm font-medium text-[var(--color-text-secondary)]">
            Step {step.number}
          </span>
        </div>

        {/* Card */}
        <div className="bg-white rounded-2xl shadow-lg overflow-hidden border border-[var(--color-border)]/50 ml-2">
          {/* Top gradient stripe */}
          <div className="h-1.5 bg-gradient-to-r from-[var(--color-primary)] to-[var(--color-primary-dark)]" />

          <div className="p-5">
            <div className="flex items-start gap-4">
              {/* Icon */}
              <div className="flex-shrink-0 w-12 h-12 rounded-full bg-[var(--color-primary)]/10 flex items-center justify-center">
                <div className="w-9 h-9 rounded-full bg-gradient-to-br from-[var(--color-primary)] to-[var(--color-primary-dark)] flex items-center justify-center shadow-sm">
                  {React.cloneElement(step.icon as React.ReactElement, {
                    className: 'w-5 h-5',
                  })}
                </div>
              </div>

              {/* Content */}
              <div className="flex-1 min-w-0">
                <h3 className="text-base font-semibold text-[var(--color-text-primary)] mb-1">
                  {step.title}
                </h3>

                {/* Time badge */}
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-[var(--color-secondary-light)]/30 text-[var(--color-secondary-dark)] text-xs font-medium mb-2">
                  <ClockIcon className="w-3 h-3" />
                  {step.timeBadge}
                </span>

                <p className="text-sm text-[var(--color-text-secondary)] leading-relaxed">
                  {step.description}
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default function HowItWorksSection() {
  const sectionRef = useRef<HTMLDivElement>(null);
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            setIsVisible(true);
            observer.disconnect();
          }
        });
      },
      {
        threshold: 0.15,
        rootMargin: '-50px',
      }
    );

    if (sectionRef.current) {
      observer.observe(sectionRef.current);
    }

    return () => observer.disconnect();
  }, []);

  return (
    <section
      id="how-it-works"
      ref={sectionRef}
      className="py-24 bg-gradient-to-b from-[var(--color-bg-secondary)] via-white to-[var(--color-bg-secondary)] relative overflow-hidden"
    >
      {/* Subtle background pattern with warm colors */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none opacity-30">
        <div className="absolute top-0 left-1/4 w-96 h-96 bg-[var(--color-primary-lighter)]/40 rounded-full blur-3xl" />
        <div className="absolute bottom-0 right-1/4 w-96 h-96 bg-[var(--color-secondary-light)]/30 rounded-full blur-3xl" />
      </div>

      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
        {/* Section header */}
        <div
          className={`text-center mb-16 ${isVisible ? 'animate-fade-in-up' : 'opacity-0'}`}
        >
          <h2 className="text-3xl sm:text-4xl font-bold text-[var(--color-text-primary)] mb-3">
            How It Works
          </h2>
          <p className="text-lg text-[var(--color-text-secondary)] max-w-xl mx-auto">
            Four steps. Minutes to setup. Lifetime of insights.
          </p>
        </div>

        {/* Desktop: Horizontal layout with chevron connectors */}
        <div className="hidden lg:block">
          <div className="flex items-stretch justify-center pt-6">
            {steps.map((step, index) => (
              <React.Fragment key={step.number}>
                <StepCard step={step} index={index} isVisible={isVisible} />
                {index < steps.length - 1 && (
                  <ChevronConnector isVisible={isVisible} delay={(index + 1) * 150 + 75} />
                )}
              </React.Fragment>
            ))}
          </div>
        </div>

        {/* Mobile: Vertical timeline layout */}
        <div className="lg:hidden space-y-8">
          {steps.map((step, index) => (
            <MobileStepCard
              key={step.number}
              step={step}
              index={index}
              isVisible={isVisible}
              isLast={index === steps.length - 1}
            />
          ))}
        </div>
      </div>
    </section>
  );
}
