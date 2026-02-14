'use client';

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { Link, AudioWaveform, Sparkles, BadgeCheck, Clock } from 'lucide-react';

// ─── Step Data ───────────────────────────────────────────────────────────────

interface StepData {
  icon: React.ReactNode;
  title: string;
  timeBadge: string;
  description: string;
}

const steps: StepData[] = [
  {
    icon: <Link className="w-5 h-5" />,
    title: 'Paste a Link',
    timeBadge: '~10 seconds',
    description:
      'Paste any YouTube URL. We pull the transcript, chapters, timestamps, and speaker info automatically.',
  },
  {
    icon: <AudioWaveform className="w-5 h-5" />,
    title: 'AI Reads Every Word',
    timeBadge: '1-3 minutes',
    description:
      'Our AI transcribes the audio with 95%+ accuracy — or uses existing captions for near-instant results.',
  },
  {
    icon: <Sparkles className="w-5 h-5" />,
    title: 'Content Gets Smarter',
    timeBadge: 'Automatic',
    description:
      'Each section is summarized, tagged, and indexed six different ways — so your questions find the right answer, not just the closest match.',
  },
  {
    icon: <BadgeCheck className="w-5 h-5" />,
    title: 'Ask. Verify. Trust.',
    timeBadge: '~4 seconds',
    description:
      'Get answers with clickable citations that jump to the exact moment in the video. Every claim is traceable.',
  },
];

const AUTOPLAY_INTERVAL = 5000;
const RESUME_DELAY = 8000;

// ─── Preview Animations ─────────────────────────────────────────────────────

function PastePreview() {
  return (
    <div className="flex flex-col gap-5 h-full justify-center">
      {/* URL Input mockup */}
      <div className="rounded-xl border border-[var(--color-border)] bg-white/80 p-4">
        <div className="text-xs text-[var(--color-text-muted)] mb-2 flex items-center gap-1.5">
          <Link className="w-3.5 h-3.5" />
          Paste a YouTube URL
        </div>
        <motion.div
          className="font-mono text-sm text-[var(--color-text-primary)] overflow-hidden whitespace-nowrap"
          initial={{ width: 0 }}
          animate={{ width: '100%' }}
          transition={{ duration: 1.5, ease: 'easeOut' }}
        >
          youtube.com/watch?v=dQw4w9WgXcQ
        </motion.div>
      </div>

      {/* Metadata card slides in */}
      <motion.div
        className="rounded-xl border border-[var(--color-border)] bg-white/80 p-4 flex items-start gap-4"
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 1.2, duration: 0.5 }}
      >
        {/* Thumbnail placeholder */}
        <div className="w-20 h-14 rounded-lg bg-gradient-to-br from-[var(--color-primary)]/20 to-[var(--color-accent)]/20 flex items-center justify-center flex-shrink-0">
          <div className="w-6 h-6 rounded-full bg-white/90 flex items-center justify-center">
            <div className="w-0 h-0 border-t-[5px] border-t-transparent border-b-[5px] border-b-transparent border-l-[8px] border-l-[var(--color-primary)] ml-0.5" />
          </div>
        </div>
        <div className="min-w-0">
          <motion.div
            className="text-sm font-medium text-[var(--color-text-primary)] truncate"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 1.6 }}
          >
            Understanding Neural Networks
          </motion.div>
          <motion.div
            className="text-xs text-[var(--color-text-muted)] mt-1 flex items-center gap-2"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 1.9 }}
          >
            <span>45:32</span>
            <span className="w-1 h-1 rounded-full bg-[var(--color-text-muted)]" />
            <span>8 chapters</span>
          </motion.div>
          <motion.div
            className="text-xs text-[var(--color-text-muted)] mt-0.5"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 2.1 }}
          >
            Tech Explained
          </motion.div>
        </div>
      </motion.div>
    </div>
  );
}

function TranscribePreview() {
  const lines = [
    { time: '0:00', text: 'Welcome everyone to today\'s deep dive...' },
    { time: '0:15', text: 'We\'ll be covering the fundamentals of...' },
    { time: '0:32', text: 'The key insight here is that neural...',  speaker: 'Dr. Smith' },
    { time: '0:45', text: 'Each layer transforms the input data...' },
  ];

  return (
    <div className="flex flex-col gap-2 h-full justify-center">
      <div className="rounded-xl border border-[var(--color-border)] bg-white/80 p-4 space-y-3">
        {lines.map((line, i) => (
          <motion.div
            key={i}
            className="flex items-start gap-3"
            initial={{ opacity: 0, x: -8 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: i * 0.6, duration: 0.4 }}
          >
            <span className="text-xs font-mono text-[var(--color-text-muted)] w-8 flex-shrink-0 pt-0.5">
              {line.time}
            </span>
            <div className="flex-1 min-w-0">
              {line.speaker && (
                <span className="inline-block text-[10px] font-medium bg-[var(--color-primary)]/10 text-[var(--color-primary)] px-1.5 py-0.5 rounded mb-1">
                  {line.speaker}
                </span>
              )}
              <p className="text-sm text-[var(--color-text-primary)] leading-relaxed">
                {line.text}
              </p>
            </div>
          </motion.div>
        ))}

        {/* Typing indicator */}
        <motion.div
          className="flex items-center gap-3 pl-11"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 2.4 }}
        >
          <div className="flex gap-1">
            {[0, 1, 2].map((i) => (
              <motion.div
                key={i}
                className="w-1.5 h-1.5 rounded-full bg-[var(--color-text-muted)]"
                animate={{ opacity: [0.3, 1, 0.3] }}
                transition={{ duration: 1.2, repeat: Infinity, delay: i * 0.2 }}
              />
            ))}
          </div>
        </motion.div>
      </div>

      {/* Accuracy badge */}
      <motion.div
        className="self-end"
        initial={{ opacity: 0, scale: 0.8 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ delay: 2.0, duration: 0.3, type: 'spring' }}
      >
        <div className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-[var(--color-primary)]/10 border border-[var(--color-primary)]/20">
          <div className="w-2 h-2 rounded-full bg-[var(--color-primary)]" />
          <span className="text-xs font-medium text-[var(--color-primary)]">
            95% accuracy
          </span>
        </div>
      </motion.div>
    </div>
  );
}

function IndexPreview() {
  const tags = ['machine learning', 'neural networks', 'optimization', 'backpropagation', 'loss function'];
  const layers = ['semantic', 'keyword', 'meaning', 'reranking', 'expansion', 'verify'];

  return (
    <div className="flex flex-col gap-4 h-full justify-center">
      {/* Chunk + tags */}
      <div className="rounded-xl border border-[var(--color-border)] bg-white/80 p-4">
        <motion.div
          className="text-xs text-[var(--color-text-muted)] mb-3"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.3 }}
        >
          Section 3 of 24
        </motion.div>

        <motion.div
          className="text-sm text-[var(--color-text-primary)] leading-relaxed mb-4"
          initial={{ opacity: 0.5 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.2 }}
        >
          &ldquo;The key principle is that each layer transforms the input data through weighted connections...&rdquo;
        </motion.div>

        {/* Tags materializing */}
        <div className="flex flex-wrap gap-2">
          {tags.map((tag, i) => (
            <motion.span
              key={tag}
              className="inline-block px-2.5 py-1 rounded-full text-xs font-medium bg-[var(--color-accent)]/10 text-[var(--color-accent-dark)] border border-[var(--color-accent)]/20"
              initial={{ opacity: 0, scale: 0.7 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: 0.8 + i * 0.25, duration: 0.3, type: 'spring' }}
            >
              {tag}
            </motion.span>
          ))}
        </div>
      </div>

      {/* 6 layers indicator */}
      <div className="rounded-xl border border-[var(--color-border)] bg-white/80 p-4">
        <div className="flex items-center gap-3 mb-2.5">
          {layers.map((_, i) => (
            <motion.div
              key={i}
              className="w-3 h-3 rounded-full"
              initial={{ backgroundColor: 'var(--color-border)' }}
              animate={{ backgroundColor: 'var(--color-primary)' }}
              transition={{ delay: 2.0 + i * 0.2, duration: 0.3 }}
            />
          ))}
        </div>
        <div className="flex flex-wrap gap-x-3 gap-y-1">
          {layers.map((layer, i) => (
            <motion.span
              key={layer}
              className="text-[11px] text-[var(--color-text-muted)]"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 2.0 + i * 0.2 }}
            >
              {layer}
            </motion.span>
          ))}
        </div>
      </div>
    </div>
  );
}

function AnswerPreview() {
  return (
    <div className="flex flex-col gap-4 h-full justify-center">
      {/* Chat bubble */}
      <div className="rounded-xl border border-[var(--color-border)] bg-white/80 p-4">
        <motion.div
          className="text-sm text-[var(--color-text-primary)] leading-relaxed"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.3, duration: 0.4 }}
        >
          The key principle discussed is that{' '}
          <motion.span
            className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-[var(--color-primary)]/10 text-[var(--color-primary)] text-xs font-medium cursor-pointer"
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 1.0, type: 'spring' }}
          >
            <span className="w-1.5 h-1.5 rounded-full bg-[var(--color-primary)]" />
            14:32
          </motion.span>{' '}
          optimization requires iterative refinement through gradient descent, where each step moves closer to the optimal solution.
        </motion.div>
      </div>

      {/* Source card with arrow */}
      <motion.div
        className="rounded-xl border border-[var(--color-primary)]/30 bg-[var(--color-primary)]/5 p-4 flex items-center gap-3"
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 1.5, duration: 0.4 }}
      >
        {/* Play button */}
        <div className="w-10 h-10 rounded-lg bg-[var(--color-primary)]/20 flex items-center justify-center flex-shrink-0">
          <div className="w-0 h-0 border-t-[5px] border-t-transparent border-b-[5px] border-b-transparent border-l-[8px] border-l-[var(--color-primary)] ml-0.5" />
        </div>
        <div>
          <div className="text-xs font-medium text-[var(--color-primary)]">
            Jump to 14:32
          </div>
          <div className="text-xs text-[var(--color-text-muted)] mt-0.5">
            &ldquo;Understanding Neural Networks&rdquo;
          </div>
          <motion.div
            className="text-[10px] text-[var(--color-text-muted)] mt-0.5"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 2.0 }}
          >
            Ch: Optimization Methods
          </motion.div>
        </div>
      </motion.div>

      {/* Traceable badge */}
      <motion.div
        className="self-start"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 2.3 }}
      >
        <div className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-[var(--color-accent)]/10 border border-[var(--color-accent)]/20">
          <BadgeCheck className="w-3 h-3 text-[var(--color-accent-dark)]" />
          <span className="text-xs font-medium text-[var(--color-accent-dark)]">
            Every claim is traceable
          </span>
        </div>
      </motion.div>
    </div>
  );
}

const previewComponents = [PastePreview, TranscribePreview, IndexPreview, AnswerPreview];

// ─── Step Tab ────────────────────────────────────────────────────────────────

function StepTab({
  step,
  index,
  isActive,
  onClick,
  progress,
}: {
  step: StepData;
  index: number;
  isActive: boolean;
  onClick: () => void;
  progress: number; // 0-100
}) {
  return (
    <button
      onClick={onClick}
      className={`w-full text-left p-5 rounded-xl transition-all duration-300 relative overflow-hidden group ${
        isActive
          ? 'bg-white shadow-lg border border-[var(--color-border)]'
          : 'bg-transparent hover:bg-white/50 border border-transparent'
      }`}
    >
      <div className="flex items-start gap-4">
        {/* Step number + icon */}
        <div
          className={`w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 transition-colors duration-300 ${
            isActive
              ? 'bg-[var(--color-primary)] text-white'
              : 'bg-[var(--color-primary)]/10 text-[var(--color-primary)] group-hover:bg-[var(--color-primary)]/20'
          }`}
        >
          {step.icon}
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-base font-semibold text-[var(--color-text-primary)]">
              {step.title}
            </span>
          </div>

          {/* Time badge */}
          <span className="inline-flex items-center gap-1 text-xs text-[var(--color-text-muted)]">
            <Clock className="w-3 h-3" />
            {step.timeBadge}
          </span>

          {/* Description - only shown when active */}
          <AnimatePresence>
            {isActive && (
              <motion.p
                className="text-sm text-[var(--color-text-secondary)] leading-relaxed mt-2"
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                transition={{ duration: 0.3 }}
              >
                {step.description}
              </motion.p>
            )}
          </AnimatePresence>
        </div>
      </div>

      {/* Progress bar */}
      {isActive && (
        <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-[var(--color-border)]">
          <motion.div
            className="h-full bg-[var(--color-primary)]"
            style={{ width: `${progress}%` }}
          />
        </div>
      )}
    </button>
  );
}

// ─── Mobile Step Card ────────────────────────────────────────────────────────

function MobileStepCard({
  step,
  index,
  isVisible,
}: {
  step: StepData;
  index: number;
  isVisible: boolean;
}) {
  const Preview = previewComponents[index];

  return (
    <motion.div
      initial={{ opacity: 0, y: 24 }}
      animate={isVisible ? { opacity: 1, y: 0 } : { opacity: 0, y: 24 }}
      transition={{ delay: index * 0.15, duration: 0.5 }}
    >
      <div className="rounded-2xl border border-[var(--color-border)] bg-white shadow-lg overflow-hidden">
        {/* Header */}
        <div className="p-5 pb-4">
          <div className="flex items-start gap-3">
            <div className="w-9 h-9 rounded-lg bg-[var(--color-primary)] text-white flex items-center justify-center flex-shrink-0">
              {step.icon}
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <h3 className="text-base font-semibold text-[var(--color-text-primary)]">
                  {step.title}
                </h3>
                <span className="inline-flex items-center gap-1 text-[11px] text-[var(--color-text-muted)]">
                  <Clock className="w-2.5 h-2.5" />
                  {step.timeBadge}
                </span>
              </div>
              <p className="text-sm text-[var(--color-text-secondary)] leading-relaxed mt-1.5">
                {step.description}
              </p>
            </div>
          </div>
        </div>

        {/* Visual preview */}
        <div className="px-5 pb-5">
          <div className="rounded-xl bg-[var(--color-bg-secondary)] p-4 min-h-[180px]">
            {isVisible && <Preview />}
          </div>
        </div>
      </div>
    </motion.div>
  );
}

// ─── Main Section ────────────────────────────────────────────────────────────

export default function HowItWorksSection() {
  const sectionRef = useRef<HTMLDivElement>(null);
  const [isVisible, setIsVisible] = useState(false);
  const [activeStep, setActiveStep] = useState(0);
  const [isPaused, setIsPaused] = useState(false);
  const [progress, setProgress] = useState(0);
  const resumeTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const progressRef = useRef<ReturnType<typeof requestAnimationFrame> | null>(null);
  const stepStartRef = useRef<number>(Date.now());

  // IntersectionObserver for scroll-triggered start
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
      { threshold: 0.15, rootMargin: '-50px' }
    );

    if (sectionRef.current) {
      observer.observe(sectionRef.current);
    }

    return () => observer.disconnect();
  }, []);

  // Progress animation using rAF
  const animateProgress = useCallback(() => {
    const elapsed = Date.now() - stepStartRef.current;
    const pct = Math.min((elapsed / AUTOPLAY_INTERVAL) * 100, 100);
    setProgress(pct);

    if (pct < 100) {
      progressRef.current = requestAnimationFrame(animateProgress);
    }
  }, []);

  // Auto-advance logic
  useEffect(() => {
    if (isPaused || !isVisible) return;

    stepStartRef.current = Date.now();
    setProgress(0);
    progressRef.current = requestAnimationFrame(animateProgress);

    const timer = setInterval(() => {
      setActiveStep((prev) => (prev + 1) % 4);
      stepStartRef.current = Date.now();
      setProgress(0);
    }, AUTOPLAY_INTERVAL);

    return () => {
      clearInterval(timer);
      if (progressRef.current) cancelAnimationFrame(progressRef.current);
    };
  }, [isPaused, isVisible, activeStep, animateProgress]);

  // Handle manual step selection
  const handleStepClick = (index: number) => {
    setActiveStep(index);
    setIsPaused(true);
    stepStartRef.current = Date.now();
    setProgress(0);

    // Clear previous resume timer
    if (resumeTimerRef.current) clearTimeout(resumeTimerRef.current);

    // Resume auto-advance after idle
    resumeTimerRef.current = setTimeout(() => {
      setIsPaused(false);
    }, RESUME_DELAY);
  };

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (resumeTimerRef.current) clearTimeout(resumeTimerRef.current);
      if (progressRef.current) cancelAnimationFrame(progressRef.current);
    };
  }, []);

  const ActivePreview = previewComponents[activeStep];

  return (
    <section
      id="how-it-works"
      ref={sectionRef}
      className="py-24 bg-gradient-to-b from-[var(--color-bg-secondary)] via-white to-[var(--color-bg-secondary)] relative overflow-hidden"
    >
      {/* Background blobs */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none opacity-30">
        <div className="absolute top-0 left-1/4 w-96 h-96 bg-[var(--color-primary-lighter)]/40 rounded-full blur-3xl" />
        <div className="absolute bottom-0 right-1/4 w-96 h-96 bg-[var(--color-secondary-light)]/30 rounded-full blur-3xl" />
      </div>

      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
        {/* Header */}
        <motion.div
          className="text-center mb-14"
          initial={{ opacity: 0, y: 20 }}
          animate={isVisible ? { opacity: 1, y: 0 } : { opacity: 0, y: 20 }}
          transition={{ duration: 0.5 }}
        >
          <h2 className="text-3xl sm:text-4xl font-bold text-[var(--color-text-primary)] mb-3">
            From Video to Verified Answer
          </h2>
          <p className="text-lg text-[var(--color-text-secondary)] max-w-xl mx-auto">
            Paste a link. Our AI does the rest. Every answer comes with proof.
          </p>
        </motion.div>

        {/* Desktop: Split panel */}
        <motion.div
          className="hidden lg:block"
          initial={{ opacity: 0, y: 24 }}
          animate={isVisible ? { opacity: 1, y: 0 } : { opacity: 0, y: 24 }}
          transition={{ duration: 0.5, delay: 0.2 }}
        >
          <div className="grid grid-cols-[340px_1fr] gap-6 items-stretch">
            {/* Left: Step tabs */}
            <div className="flex flex-col gap-2">
              {steps.map((step, index) => (
                <StepTab
                  key={index}
                  step={step}
                  index={index}
                  isActive={activeStep === index}
                  onClick={() => handleStepClick(index)}
                  progress={activeStep === index ? progress : 0}
                />
              ))}
            </div>

            {/* Right: Animated preview */}
            <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-bg-secondary)] p-8 min-h-[420px] relative overflow-hidden">
              <AnimatePresence mode="wait">
                <motion.div
                  key={activeStep}
                  className="h-full"
                  initial={{ opacity: 0, x: 20 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -20 }}
                  transition={{ duration: 0.35 }}
                >
                  <ActivePreview />
                </motion.div>
              </AnimatePresence>
            </div>
          </div>
        </motion.div>

        {/* Mobile: Stacked cards */}
        <div className="lg:hidden space-y-6">
          {steps.map((step, index) => (
            <MobileStepCard
              key={index}
              step={step}
              index={index}
              isVisible={isVisible}
            />
          ))}
        </div>

        {/* Footer */}
        <motion.p
          className="text-center text-sm text-[var(--color-text-muted)] mt-12 max-w-xl mx-auto"
          initial={{ opacity: 0 }}
          animate={isVisible ? { opacity: 1 } : { opacity: 0 }}
          transition={{ delay: 0.8 }}
        >
          Powered by semantic search, AI reranking, and cross-source synthesis — working together on every question.
        </motion.p>
      </div>
    </section>
  );
}
