'use client';

import React, { useState, useEffect, useRef } from 'react';
import { motion, type Variants, AnimatePresence } from 'framer-motion';

// Animation variants - restrained, professional
const containerVariants: Variants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.1,
      delayChildren: 0.1,
    },
  },
};

const fadeInVariants: Variants = {
  hidden: { opacity: 0, y: 16 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.5, ease: 'easeOut' },
  },
};

const pillarVariants: Variants = {
  hidden: { opacity: 0, y: 20 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.4, ease: 'easeOut' },
  },
};

const statsContainerVariants: Variants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.08,
      delayChildren: 0.3,
    },
  },
};

export default function TechnologySection() {
  return (
    <section
      id="technology"
      className="py-24 bg-gradient-to-b from-white via-[var(--color-bg-secondary)] to-white relative overflow-hidden"
    >
      {/* Subtle background pattern */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none opacity-30">
        <div className="absolute top-0 right-1/4 w-96 h-96 bg-[var(--color-primary-lighter)]/40 rounded-full blur-3xl" />
        <div className="absolute bottom-0 left-1/4 w-96 h-96 bg-[var(--color-secondary-light)]/30 rounded-full blur-3xl" />
      </div>

      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
        {/* Header */}
        <motion.div
          className="text-center mb-12"
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, amount: 0.5 }}
          variants={fadeInVariants}
        >
          <h2 className="text-3xl md:text-4xl font-bold text-[var(--color-text-primary)] mb-3">
            Every Answer Comes with Proof
          </h2>
          <p className="text-[var(--color-text-secondary)] max-w-2xl mx-auto text-lg">
            Ask a question. Get an answer from across your entire library.
            Click any citation to see exactly where it came from.
          </p>
        </motion.div>

        {/* Mock Product UI */}
        <motion.div
          className="mb-16"
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, amount: 0.3 }}
          variants={fadeInVariants}
        >
          <MockProductUI />
        </motion.div>

        {/* Four Pillars */}
        <motion.div
          className="grid md:grid-cols-2 gap-6 mb-16"
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, amount: 0.2 }}
          variants={containerVariants}
        >
          <motion.div variants={pillarVariants}>
            <PillarCard
              icon={<LibraryIcon />}
              headline="Nothing gets missed"
              body="When you ask a question, we search every video you've added—not just the closest match. You get perspectives from across your collection, synthesized into one coherent answer."
              accentColor="primary"
            />
          </motion.div>

          <motion.div variants={pillarVariants}>
            <PillarCard
              icon={<VerifyIcon />}
              headline="Verify any claim in one click"
              body="Every answer includes citations with timestamps, speaker names, and chapter context. One click takes you to the exact moment in the video."
              accentColor="accent"
            />
          </motion.div>

          <motion.div variants={pillarVariants}>
            <PillarCard
              icon={<UnderstandIcon />}
              headline="Ask however you think. Get exactly what you need."
              body="Ask for a summary, get a synthesis. Ask for a specific fact, get the exact timestamp. The system understands what kind of answer you need."
              accentColor="secondary"
            />
          </motion.div>

          <motion.div variants={pillarVariants}>
            <PillarCard
              icon={<CoherentIcon />}
              headline="It remembers what matters to you"
              body="In long research sessions, the system remembers what you've established. You can see exactly what it remembers — and edit or delete any fact. No need to repeat yourself or start over."
              accentColor="primary"
            />
          </motion.div>
        </motion.div>

        {/* Stats */}
        <motion.div
          className="grid grid-cols-2 md:grid-cols-4 gap-8 max-w-3xl mx-auto"
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, amount: 0.5 }}
          variants={statsContainerVariants}
        >
          <motion.div variants={fadeInVariants}>
            <Stat value="Avg. 4" label="Sources per answer" />
          </motion.div>
          <motion.div variants={fadeInVariants}>
            <Stat value="Every" label="Video checked" />
          </motion.div>
          <motion.div variants={fadeInVariants}>
            <Stat value="Seconds" label="To get answers" />
          </motion.div>
          <motion.div variants={fadeInVariants}>
            <Stat value="100%" label="Verifiable" />
          </motion.div>
        </motion.div>
      </div>
    </section>
  );
}

// === Animated Mock Product UI ===

interface ConversationTurn {
  question: string;
  answerParts: readonly AnswerPart[];
  sources: readonly Source[];
}

type AnswerPart =
  | { readonly type: 'text'; readonly content: string }
  | { readonly type: 'citation'; readonly timestamp: string; readonly sourceIndex: number };

interface Source {
  videoTitle: string;
  speaker: string;
  timestamp: string;
  chapter: string;
}

const CONVERSATION_TURNS: ConversationTurn[] = [
  {
    question: "What do the experts say about market timing?",
    answerParts: [
      { type: 'text', content: "The consensus across your library is that timing the market consistently is extremely difficult. " },
      { type: 'citation', timestamp: "14:32", sourceIndex: 0 },
      { type: 'text', content: " argues that most investors underperform by trying to time entries and exits. However, " },
      { type: 'citation', timestamp: "8:45", sourceIndex: 1 },
      { type: 'text', content: " notes that understanding cycles can help with asset allocation decisions..." },
    ],
    sources: [
      { videoTitle: "Investing Fundamentals", speaker: "John Bogle", timestamp: "14:32", chapter: "The Futility of Market Timing" },
      { videoTitle: "Market Cycles Explained", speaker: "Ray Dalio", timestamp: "8:45", chapter: "Understanding Economic Cycles" },
      { videoTitle: "Warren Buffett Annual Meeting", speaker: "Warren Buffett", timestamp: "1:24:08", chapter: "Q&A on Market Valuations" },
    ],
  },
  {
    question: "What did Bogle specifically say about this?",
    answerParts: [
      { type: 'text', content: "Bogle emphasized that " },
      { type: 'citation', timestamp: "14:32", sourceIndex: 0 },
      { type: 'text', content: " \"the idea that you can consistently time the market is an illusion.\" He backed this with data showing " },
      { type: 'citation', timestamp: "16:45", sourceIndex: 1 },
      { type: 'text', content: " that over 90% of active managers fail to beat index funds over 15-year periods." },
    ],
    sources: [
      { videoTitle: "Investing Fundamentals", speaker: "John Bogle", timestamp: "14:32", chapter: "The Futility of Market Timing" },
      { videoTitle: "Investing Fundamentals", speaker: "John Bogle", timestamp: "16:45", chapter: "Index Fund Performance Data" },
    ],
  },
  {
    question: "Summarize the key investment principles",
    answerParts: [
      { type: 'text', content: "Based on your video library, here are the core principles: 1) Stay invested long-term " },
      { type: 'citation', timestamp: "22:15", sourceIndex: 0 },
      { type: 'text', content: ", 2) Diversify across asset classes " },
      { type: 'citation', timestamp: "31:20", sourceIndex: 1 },
      { type: 'text', content: ", 3) Keep costs low " },
      { type: 'citation', timestamp: "8:10", sourceIndex: 2 },
      { type: 'text', content: ", and 4) Ignore short-term noise." },
    ],
    sources: [
      { videoTitle: "The Psychology of Money", speaker: "Morgan Housel", timestamp: "22:15", chapter: "Time in Market vs Timing" },
      { videoTitle: "Asset Allocation Guide", speaker: "Rick Ferri", timestamp: "31:20", chapter: "Building a Balanced Portfolio" },
      { videoTitle: "Investing Fundamentals", speaker: "John Bogle", timestamp: "8:10", chapter: "The Cost Matters Hypothesis" },
    ],
  },
];

type AnimationPhase = 'idle' | 'typing-question' | 'thinking' | 'streaming' | 'sources' | 'pause' | 'click-citation' | 'show-video' | 'transition';

function MockProductUI() {
  const [phase, setPhase] = useState<AnimationPhase>('idle');
  const [turnIndex, setTurnIndex] = useState(0);
  const [questionText, setQuestionText] = useState('');
  const [visibleAnswerParts, setVisibleAnswerParts] = useState(0);
  const [streamedText, setStreamedText] = useState('');
  const [visibleSources, setVisibleSources] = useState(0);
  const [clickedCitationIndex, setClickedCitationIndex] = useState<number | null>(null);
  const [highlightedSourceIndex, setHighlightedSourceIndex] = useState<number | null>(null);
  const [showVideoPreview, setShowVideoPreview] = useState(false);
  const [hasStarted, setHasStarted] = useState(false);
  const [conversationHistory, setConversationHistory] = useState<Array<{ question: string; answer: React.ReactNode }>>([]);
  const containerRef = useRef<HTMLDivElement>(null);

  const currentTurn = CONVERSATION_TURNS[turnIndex];

  // Start animation when component comes into view
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && !hasStarted) {
          setHasStarted(true);
          setTimeout(() => setPhase('typing-question'), 500);
        }
      },
      { threshold: 0.3 }
    );

    if (containerRef.current) {
      observer.observe(containerRef.current);
    }

    return () => observer.disconnect();
  }, [hasStarted]);

  // Question typing animation
  useEffect(() => {
    if (phase !== 'typing-question') return;

    let index = 0;
    const question = currentTurn.question;
    const interval = setInterval(() => {
      if (index < question.length) {
        setQuestionText(question.slice(0, index + 1));
        index++;
      } else {
        clearInterval(interval);
        setTimeout(() => setPhase('thinking'), 300);
      }
    }, 30);

    return () => clearInterval(interval);
  }, [phase, currentTurn.question]);

  // Thinking phase
  useEffect(() => {
    if (phase !== 'thinking') return;
    const timeout = setTimeout(() => setPhase('streaming'), 1000);
    return () => clearTimeout(timeout);
  }, [phase]);

  // Answer streaming animation
  useEffect(() => {
    if (phase !== 'streaming') return;

    let partIndex = 0;
    let charIndex = 0;
    const answerParts = currentTurn.answerParts;

    const streamNext = () => {
      if (partIndex >= answerParts.length) {
        setTimeout(() => setPhase('sources'), 300);
        return;
      }

      const currentPart = answerParts[partIndex];

      if (currentPart.type === 'citation') {
        setVisibleAnswerParts(partIndex + 1);
        partIndex++;
        setTimeout(streamNext, 150);
      } else {
        if (charIndex < currentPart.content.length) {
          setStreamedText(prev => prev + currentPart.content[charIndex]);
          charIndex++;
          setTimeout(streamNext, 12);
        } else {
          setVisibleAnswerParts(partIndex + 1);
          partIndex++;
          charIndex = 0;
          streamNext();
        }
      }
    };

    streamNext();
  }, [phase, currentTurn.answerParts]);

  // Sources reveal animation
  useEffect(() => {
    if (phase !== 'sources') return;

    let index = 0;
    const sources = currentTurn.sources;
    const interval = setInterval(() => {
      if (index < sources.length) {
        setVisibleSources(index + 1);
        index++;
      } else {
        clearInterval(interval);
        setPhase('pause');
      }
    }, 120);

    return () => clearInterval(interval);
  }, [phase, currentTurn.sources]);

  // Pause before citation click
  useEffect(() => {
    if (phase !== 'pause') return;
    const timeout = setTimeout(() => setPhase('click-citation'), 1500);
    return () => clearTimeout(timeout);
  }, [phase]);

  // Citation click animation
  useEffect(() => {
    if (phase !== 'click-citation') return;

    // Find first citation in current turn
    const firstCitationIdx = currentTurn.answerParts.findIndex(p => p.type === 'citation');
    if (firstCitationIdx === -1) {
      setPhase('transition');
      return;
    }

    setClickedCitationIndex(firstCitationIdx);

    const timeout1 = setTimeout(() => {
      const citationPart = currentTurn.answerParts[firstCitationIdx];
      if (citationPart.type === 'citation') {
        setHighlightedSourceIndex(citationPart.sourceIndex);
      }
    }, 300);

    const timeout2 = setTimeout(() => {
      setShowVideoPreview(true);
    }, 800);

    const timeout3 = setTimeout(() => {
      setPhase('show-video');
    }, 1000);

    return () => {
      clearTimeout(timeout1);
      clearTimeout(timeout2);
      clearTimeout(timeout3);
    };
  }, [phase, currentTurn.answerParts]);

  // Show video preview phase
  useEffect(() => {
    if (phase !== 'show-video') return;

    const timeout = setTimeout(() => {
      setShowVideoPreview(false);
      setClickedCitationIndex(null);
      setHighlightedSourceIndex(null);
      setPhase('transition');
    }, 2500);

    return () => clearTimeout(timeout);
  }, [phase]);

  // Transition to next turn or restart
  useEffect(() => {
    if (phase !== 'transition') return;

    const timeout = setTimeout(() => {
      // Save current turn to history (simplified) - inline the answer rendering
      const currentAnswer = currentTurn.answerParts.map((part, i) => {
        if (part.type === 'text') {
          return <span key={i}>{part.content}</span>;
        } else {
          return <CitationBadge key={i} timestamp={part.timestamp} isSmall />;
        }
      });

      setConversationHistory(prev => [
        ...prev.slice(-1), // Keep only last turn in history for space
        { question: currentTurn.question, answer: currentAnswer }
      ]);

      // Move to next turn or restart
      const nextTurn = (turnIndex + 1) % CONVERSATION_TURNS.length;
      setTurnIndex(nextTurn);

      // Reset state for next turn
      setQuestionText('');
      setVisibleAnswerParts(0);
      setStreamedText('');
      setVisibleSources(0);

      if (nextTurn === 0) {
        // Full restart - clear history
        setConversationHistory([]);
      }

      setPhase('typing-question');
    }, 1000);

    return () => clearTimeout(timeout);
  }, [phase, turnIndex, currentTurn.question, currentTurn.answerParts]);

  // Render the streamed answer content
  const renderAnswerContent = () => {
    const elements: React.ReactNode[] = [];
    let textBuffer = '';
    const answerParts = currentTurn.answerParts;

    for (let i = 0; i < visibleAnswerParts; i++) {
      const part = answerParts[i];
      if (part.type === 'text') {
        textBuffer += part.content;
      } else if (part.type === 'citation') {
        if (textBuffer) {
          elements.push(<span key={`text-${i}`}>{textBuffer}</span>);
          textBuffer = '';
        }
        const isClicked = clickedCitationIndex === i;
        elements.push(
          <motion.span
            key={`citation-${i}`}
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{
              opacity: 1,
              scale: isClicked ? 1.1 : 1,
            }}
            transition={{ duration: 0.2 }}
          >
            <CitationBadge
              timestamp={part.timestamp}
              isHighlighted={isClicked}
            />
          </motion.span>
        );
      }
    }

    // Add currently streaming text
    if (phase === 'streaming' && visibleAnswerParts < answerParts.length) {
      const currentPart = answerParts[visibleAnswerParts];
      if (currentPart.type === 'text') {
        let previousTextLength = 0;
        for (let i = 0; i < visibleAnswerParts; i++) {
          const prevPart = answerParts[i];
          if (prevPart.type === 'text') {
            previousTextLength += prevPart.content.length;
          }
        }
        const streamedForCurrentPart = streamedText.slice(previousTextLength);
        textBuffer += streamedForCurrentPart;
      }
    }

    if (textBuffer) {
      elements.push(<span key="text-final">{textBuffer}</span>);
    }

    if (phase === 'streaming') {
      elements.push(
        <span key="cursor" className="inline-block w-0.5 h-4 bg-[var(--color-primary)] ml-0.5 animate-pulse" />
      );
    }

    return elements;
  };

  return (
    <div className="max-w-3xl mx-auto" ref={containerRef}>
      {/* Subtle context label */}
      <div className="flex items-center justify-center gap-2 mb-3">
        <div className="h-px flex-1 max-w-[60px] bg-[var(--color-border)]" />
        <span className="text-xs text-[var(--color-text-tertiary)] tracking-wide">Live preview</span>
        <div className="h-px flex-1 max-w-[60px] bg-[var(--color-border)]" />
      </div>

      <div className="bg-white rounded-2xl border border-[var(--color-border)]/50 overflow-hidden shadow-lg relative">
        {/* Top gradient stripe */}
        <div className="h-1.5 bg-gradient-to-r from-[var(--color-primary)] to-[var(--color-primary-dark)]" />

        {/* Video preview overlay */}
        <AnimatePresence>
          {showVideoPreview && highlightedSourceIndex !== null && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="absolute inset-0 z-20 bg-black/90 flex items-center justify-center p-6"
            >
              <div className="w-full max-w-md">
                {/* Mock video player */}
                <div className="bg-gray-900 rounded-lg overflow-hidden shadow-2xl">
                  {/* Video area */}
                  <div className="aspect-video bg-gradient-to-br from-gray-800 to-gray-900 relative flex items-center justify-center">
                    {/* Play button overlay */}
                    <div className="absolute inset-0 flex items-center justify-center">
                      <motion.div
                        initial={{ scale: 0 }}
                        animate={{ scale: 1 }}
                        transition={{ delay: 0.2, type: "spring" }}
                        className="w-16 h-16 bg-[var(--color-primary)] rounded-full flex items-center justify-center shadow-lg"
                      >
                        <svg className="w-6 h-6 text-white ml-1" fill="currentColor" viewBox="0 0 24 24">
                          <path d="M8 5.14v14l11-7-11-7z" />
                        </svg>
                      </motion.div>
                    </div>
                    {/* Timestamp indicator */}
                    <motion.div
                      initial={{ opacity: 0, x: -20 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: 0.4 }}
                      className="absolute bottom-3 left-3 px-2 py-1 bg-black/70 rounded text-white text-xs font-mono"
                    >
                      {currentTurn.sources[highlightedSourceIndex]?.timestamp}
                    </motion.div>
                  </div>
                  {/* Video info */}
                  <div className="p-3 bg-gray-800">
                    <motion.p
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      transition={{ delay: 0.3 }}
                      className="text-white text-sm font-medium truncate"
                    >
                      {currentTurn.sources[highlightedSourceIndex]?.videoTitle}
                    </motion.p>
                    <motion.p
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      transition={{ delay: 0.4 }}
                      className="text-gray-400 text-xs mt-0.5"
                    >
                      {currentTurn.sources[highlightedSourceIndex]?.chapter}
                    </motion.p>
                  </div>
                </div>
                {/* Instruction text */}
                <motion.p
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: 0.5 }}
                  className="text-center text-gray-400 text-xs mt-3"
                >
                  Jump to exact moment in video
                </motion.p>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Conversation history */}
        <AnimatePresence>
          {conversationHistory.length > 0 && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              className="border-b border-[var(--color-border)]/50 bg-[var(--color-bg-secondary)]/30"
            >
              {conversationHistory.map((turn, idx) => (
                <div key={idx} className="p-3 border-b border-[var(--color-border)]/30 last:border-b-0">
                  <p className="text-xs text-[var(--color-text-tertiary)] mb-1">Previous question</p>
                  <p className="text-sm text-[var(--color-text-primary)] font-medium mb-2">{turn.question}</p>
                  <p className="text-xs text-[var(--color-text-secondary)] line-clamp-2">{turn.answer}</p>
                </div>
              ))}
            </motion.div>
          )}
        </AnimatePresence>

        {/* Current question bar */}
        <div className="border-b border-[var(--color-border)]/50 p-4">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-[var(--color-primary)]/10 flex items-center justify-center flex-shrink-0">
              <svg className="w-4 h-4 text-[var(--color-primary)]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M8.625 12a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H8.25m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H12m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0h-.375M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <div className="flex-1 min-h-[24px]">
              {phase === 'idle' ? (
                <div className="h-4 w-48 bg-[var(--color-border)]/30 rounded animate-pulse" />
              ) : (
                <p className="text-[var(--color-text-primary)] text-sm md:text-base font-medium">
                  {questionText}
                  {phase === 'typing-question' && (
                    <span className="inline-block w-0.5 h-4 bg-[var(--color-text-primary)] ml-0.5 animate-pulse" />
                  )}
                </p>
              )}
            </div>
            {/* Turn indicator */}
            {phase !== 'idle' && (
              <div className="flex gap-1">
                {CONVERSATION_TURNS.map((_, idx) => (
                  <div
                    key={idx}
                    className={`w-1.5 h-1.5 rounded-full transition-colors ${
                      idx === turnIndex ? 'bg-[var(--color-primary)]' : 'bg-[var(--color-border)]'
                    }`}
                  />
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Answer content */}
        <div className="p-4 md:p-6 min-h-[260px]">
          {(phase === 'idle' || phase === 'typing-question') && (
            <div className="space-y-3">
              <div className="h-4 w-full bg-[var(--color-border)]/20 rounded" />
              <div className="h-4 w-5/6 bg-[var(--color-border)]/20 rounded" />
              <div className="h-4 w-4/6 bg-[var(--color-border)]/20 rounded" />
            </div>
          )}

          {phase === 'thinking' && (
            <div className="flex items-center gap-2 text-[var(--color-text-secondary)]">
              <div className="flex gap-1">
                <span className="w-2 h-2 bg-[var(--color-primary)] rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                <span className="w-2 h-2 bg-[var(--color-primary)] rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                <span className="w-2 h-2 bg-[var(--color-primary)] rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
              </div>
              <span className="text-sm">Searching {turnIndex === 0 ? 'your videos' : 'for more details'}...</span>
            </div>
          )}

          {!['idle', 'typing-question', 'thinking'].includes(phase) && (
            <>
              <p className="text-[var(--color-text-secondary)] text-sm md:text-base leading-relaxed mb-4">
                {renderAnswerContent()}
              </p>

              {/* Citation details */}
              <AnimatePresence>
                {visibleSources > 0 && (
                  <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="mt-6 space-y-3"
                  >
                    <p className="text-xs text-[var(--color-text-secondary)] uppercase tracking-wide font-medium mb-2">Sources</p>
                    <div className="grid gap-2">
                      {currentTurn.sources.slice(0, visibleSources).map((source, index) => (
                        <motion.div
                          key={index}
                          initial={{ opacity: 0, x: -10 }}
                          animate={{
                            opacity: 1,
                            x: 0,
                            scale: highlightedSourceIndex === index ? 1.02 : 1,
                          }}
                          transition={{ delay: index * 0.05 }}
                        >
                          <CitationRow
                            {...source}
                            isHighlighted={highlightedSourceIndex === index}
                          />
                        </motion.div>
                      ))}
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

// Inline citation badge (compact)
function CitationBadge({
  timestamp,
  isHighlighted,
  isSmall,
}: {
  timestamp: string;
  isHighlighted?: boolean;
  isSmall?: boolean;
}) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded font-medium cursor-pointer transition-all ${
        isSmall ? 'px-1 py-0.5 text-[10px]' : 'px-1.5 py-0.5 text-xs'
      } ${
        isHighlighted
          ? 'bg-[var(--color-accent)] border-[var(--color-accent)] text-white shadow-md'
          : 'bg-[var(--color-primary)]/10 border border-[var(--color-primary)]/30 text-[var(--color-primary)] hover:bg-[var(--color-primary)]/20'
      }`}
    >
      <svg className={isSmall ? 'w-2.5 h-2.5' : 'w-3 h-3'} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
        <path strokeLinecap="round" strokeLinejoin="round" d="M13.19 8.688a4.5 4.5 0 011.242 7.244l-4.5 4.5a4.5 4.5 0 01-6.364-6.364l1.757-1.757m9.193-9.193a4.5 4.5 0 00-6.364 6.364l4.5 4.5a4.5 4.5 0 006.364-6.364l-1.757-1.757" />
      </svg>
      {timestamp}
    </span>
  );
}

// Citation row for expanded view
function CitationRow({
  videoTitle,
  speaker,
  timestamp,
  chapter,
  isHighlighted,
}: {
  videoTitle: string;
  speaker: string;
  timestamp: string;
  chapter: string;
  isHighlighted?: boolean;
}) {
  return (
    <div
      className={`flex items-center gap-3 p-2.5 rounded-lg border transition-all cursor-pointer group ${
        isHighlighted
          ? 'bg-[var(--color-accent)]/10 border-[var(--color-accent)]/50 shadow-md'
          : 'bg-[var(--color-bg-secondary)]/50 border-[var(--color-border)]/30 hover:border-[var(--color-primary)]/30'
      }`}
    >
      {/* Play icon */}
      <div
        className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 transition-colors ${
          isHighlighted
            ? 'bg-[var(--color-accent)] border-[var(--color-accent)]'
            : 'bg-[var(--color-accent)]/10 border border-[var(--color-accent)]/30 group-hover:bg-[var(--color-accent)]/20'
        }`}
      >
        <svg
          className={`w-3.5 h-3.5 ml-0.5 ${isHighlighted ? 'text-white' : 'text-[var(--color-accent)]'}`}
          fill="currentColor"
          viewBox="0 0 24 24"
        >
          <path d="M8 5.14v14l11-7-11-7z" />
        </svg>
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 text-sm">
          <span className="text-[var(--color-text-primary)] font-medium truncate">{videoTitle}</span>
          <span className="text-[var(--color-border)]">•</span>
          <span className="text-[var(--color-text-secondary)]">{speaker}</span>
        </div>
        <div className="flex items-center gap-2 text-xs text-[var(--color-text-secondary)] mt-0.5">
          <span>{chapter}</span>
          <span className="text-[var(--color-border)]">@</span>
          <span className={`font-medium ${isHighlighted ? 'text-[var(--color-accent)]' : 'text-[var(--color-primary)]'}`}>
            {timestamp}
          </span>
        </div>
      </div>

      {/* Jump arrow - always visible when highlighted */}
      <div className={`flex-shrink-0 transition-opacity ${isHighlighted ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'}`}>
        <svg className="w-4 h-4 text-[var(--color-text-secondary)]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
          <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 6H5.25A2.25 2.25 0 003 8.25v10.5A2.25 2.25 0 005.25 21h10.5A2.25 2.25 0 0018 18.75V10.5m-10.5 6L21 3m0 0h-5.25M21 3v5.25" />
        </svg>
      </div>
    </div>
  );
}

// === Pillar Card ===
function PillarCard({
  icon,
  headline,
  body,
  accentColor,
}: {
  icon: React.ReactNode;
  headline: string;
  body: string;
  accentColor: 'primary' | 'secondary' | 'accent';
}) {
  const colorClasses = {
    primary: 'bg-[var(--color-primary)]/10 border-[var(--color-primary)]/20 text-[var(--color-primary)]',
    secondary: 'bg-[var(--color-secondary-light)]/30 border-[var(--color-secondary)]/30 text-[var(--color-secondary-dark)]',
    accent: 'bg-[var(--color-accent)]/10 border-[var(--color-accent)]/20 text-[var(--color-accent)]',
  };

  return (
    <div className="p-6 bg-white rounded-xl border border-[var(--color-border)]/50 hover:border-[var(--color-primary)]/30 hover:shadow-md transition-all h-full">
      <div className="flex items-start gap-4">
        {/* Icon */}
        <div
          className={`w-10 h-10 rounded-lg border flex items-center justify-center flex-shrink-0 ${colorClasses[accentColor]}`}
        >
          <div className="w-5 h-5">{icon}</div>
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <h3 className="text-[var(--color-text-primary)] font-semibold text-base mb-2">{headline}</h3>
          <p className="text-[var(--color-text-secondary)] text-sm leading-relaxed">{body}</p>
        </div>
      </div>
    </div>
  );
}

// === Stat ===
function Stat({ value, label }: { value: string; label: string }) {
  return (
    <div className="text-center">
      <div className="text-2xl font-bold text-[var(--color-text-primary)]">{value}</div>
      <div className="text-xs text-[var(--color-text-secondary)]">{label}</div>
    </div>
  );
}

// === Icons ===

// Library/collection icon - for "Complete"
function LibraryIcon() {
  return (
    <svg
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth="1.5"
      className="w-full h-full"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M3.75 6A2.25 2.25 0 016 3.75h2.25A2.25 2.25 0 0110.5 6v2.25a2.25 2.25 0 01-2.25 2.25H6a2.25 2.25 0 01-2.25-2.25V6zM3.75 15.75A2.25 2.25 0 016 13.5h2.25a2.25 2.25 0 012.25 2.25V18a2.25 2.25 0 01-2.25 2.25H6A2.25 2.25 0 013.75 18v-2.25zM13.5 6a2.25 2.25 0 012.25-2.25H18A2.25 2.25 0 0120.25 6v2.25A2.25 2.25 0 0118 10.5h-2.25a2.25 2.25 0 01-2.25-2.25V6zM13.5 15.75a2.25 2.25 0 012.25-2.25H18a2.25 2.25 0 012.25 2.25V18A2.25 2.25 0 0118 20.25h-2.25A2.25 2.25 0 0113.5 18v-2.25z"
      />
    </svg>
  );
}

// Checkmark in circle - for "Verifiable"
function VerifyIcon() {
  return (
    <svg
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth="1.5"
      className="w-full h-full"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
      />
    </svg>
  );
}

// Lightbulb - for "Understood"
function UnderstandIcon() {
  return (
    <svg
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth="1.5"
      className="w-full h-full"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M12 18v-5.25m0 0a6.01 6.01 0 001.5-.189m-1.5.189a6.01 6.01 0 01-1.5-.189m3.75 7.478a12.06 12.06 0 01-4.5 0m3.75 2.383a14.406 14.406 0 01-3 0M14.25 18v-.192c0-.983.658-1.823 1.508-2.316a7.5 7.5 0 10-7.517 0c.85.493 1.509 1.333 1.509 2.316V18"
      />
    </svg>
  );
}

// Arrows for context/memory - for "Coherent"
function CoherentIcon() {
  return (
    <svg
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth="1.5"
      className="w-full h-full"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M7.5 21L3 16.5m0 0L7.5 12M3 16.5h13.5m0-13.5L21 7.5m0 0L16.5 12M21 7.5H7.5"
      />
    </svg>
  );
}
