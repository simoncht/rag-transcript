'use client';

import React, { useRef, useState, useEffect } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import Card from '../shared/Card';

interface Testimonial {
  quote: string;
  name: string;
  role: string;
  avatar: string;
}

const testimonials: Testimonial[] = [
  {
    quote: "The citation accuracy is incredible. Every quote links directly to the exact moment in the video. It's transformed how I write research papers.",
    name: 'Dr. Sarah Chen',
    role: 'Research Scientist',
    avatar: 'SC',
  },
  {
    quote: "I used to spend hours rewatching lectures before exams. Now I just ask questions and get answers with timestamps. My study time dropped by 60%.",
    name: 'Marcus Johnson',
    role: 'Graduate Student',
    avatar: 'MJ',
  },
  {
    quote: "We indexed 200+ hours of training videos. New hires can now find any procedure in seconds instead of watching entire videos.",
    name: 'Emily Rodriguez',
    role: 'L&D Manager',
    avatar: 'ER',
  },
  {
    quote: "I run a podcast and needed to repurpose old episodes into blog posts. This tool found the best quotes and gave me exact timestamps. Saved me 20+ hours a month.",
    name: 'Jake Morrison',
    role: 'Podcast Host',
    avatar: 'JM',
  },
  {
    quote: "Our legal team uses this to review deposition videos. Being able to search for specific statements with timestamps has been a game-changer for case prep.",
    name: 'Amanda Foster',
    role: 'Paralegal',
    avatar: 'AF',
  },
  {
    quote: "I teach online courses and my students constantly ask questions covered in past lectures. Now I just point them to the searchable archive. Support tickets down 70%.",
    name: 'Prof. David Kim',
    role: 'Online Educator',
    avatar: 'DK',
  },
  {
    quote: "As a journalist, I interview people for hours. Finding that one perfect soundbite used to take forever. Now it's instant. This is essential for my workflow.",
    name: 'Rachel Torres',
    role: 'Investigative Journalist',
    avatar: 'RT',
  },
  {
    quote: "We archive all our company town halls. When someone asks 'didn't the CEO mention X?', we can find and share the exact clip in seconds.",
    name: 'Michael Park',
    role: 'Internal Comms Director',
    avatar: 'MP',
  },
  {
    quote: "I'm building a course from YouTube tutorials I've collected over years. This tool helped me organize 500+ videos into a searchable curriculum. Incredible.",
    name: 'Lisa Nguyen',
    role: 'Course Creator',
    avatar: 'LN',
  },
  {
    quote: "Our UX team records every user interview. Being able to search across all sessions for mentions of specific features has transformed our research synthesis.",
    name: 'Chris Anderson',
    role: 'UX Research Lead',
    avatar: 'CA',
  },
  {
    quote: "I'm a med student with 100+ hours of recorded lectures. Searching for 'mitral valve' across all of them and getting timestamped results? Life-changing.",
    name: 'Priya Sharma',
    role: 'Medical Student',
    avatar: 'PS',
  },
  {
    quote: "We use this for our YouTube channel analytics deep-dives. Finding every time we mentioned a topic across 3 years of content takes seconds, not days.",
    name: 'Tom Bradley',
    role: 'Content Strategist',
    avatar: 'TB',
  },
];

export default function TestimonialsSection() {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [canScrollLeft, setCanScrollLeft] = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(true);

  const checkScrollPosition = () => {
    if (scrollRef.current) {
      const { scrollLeft, scrollWidth, clientWidth } = scrollRef.current;
      setCanScrollLeft(scrollLeft > 0);
      setCanScrollRight(scrollLeft < scrollWidth - clientWidth - 10);
    }
  };

  useEffect(() => {
    checkScrollPosition();
    const scrollElement = scrollRef.current;
    if (scrollElement) {
      scrollElement.addEventListener('scroll', checkScrollPosition);
      return () => scrollElement.removeEventListener('scroll', checkScrollPosition);
    }
  }, []);

  const scroll = (direction: 'left' | 'right') => {
    if (scrollRef.current) {
      const scrollAmount = 400;
      scrollRef.current.scrollBy({
        left: direction === 'left' ? -scrollAmount : scrollAmount,
        behavior: 'smooth',
      });
    }
  };

  return (
    <section className="py-20 bg-gray-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Section header */}
        <div className="text-center mb-12">
          <h2 className="text-4xl font-bold text-gray-900 mb-4">
            Loved by Researchers and Professionals
          </h2>
          <p className="text-xl text-gray-600 max-w-2xl mx-auto">
            See how teams are transforming their video content into searchable knowledge.
          </p>
        </div>

        {/* Carousel container */}
        <div className="relative">
          {/* Left arrow */}
          <button
            onClick={() => scroll('left')}
            disabled={!canScrollLeft}
            className={`absolute left-0 top-1/2 -translate-y-1/2 -translate-x-4 z-10 w-12 h-12 rounded-full bg-white shadow-lg flex items-center justify-center transition-all duration-200 ${
              canScrollLeft
                ? 'opacity-100 hover:bg-gray-50 hover:scale-110 cursor-pointer'
                : 'opacity-0 cursor-default'
            }`}
            aria-label="Scroll left"
          >
            <ChevronLeft className="w-6 h-6 text-gray-600" />
          </button>

          {/* Scrollable container */}
          <div
            ref={scrollRef}
            className="flex gap-6 overflow-x-auto scrollbar-hide scroll-smooth pb-4"
            style={{ scrollbarWidth: 'none', msOverflowStyle: 'none' }}
          >
            {testimonials.map((testimonial, index) => (
              <div key={index} className="flex-shrink-0 w-[350px]">
                <Card className="h-full flex flex-col">
                  {/* Quote icon */}
                  <div className="mb-4">
                    <svg className="w-8 h-8 text-primary/30" fill="currentColor" viewBox="0 0 24 24">
                      <path d="M14.017 21v-7.391c0-5.704 3.731-9.57 8.983-10.609l.995 2.151c-2.432.917-3.995 3.638-3.995 5.849h4v10h-9.983zm-14.017 0v-7.391c0-5.704 3.748-9.57 9-10.609l.996 2.151c-2.433.917-3.996 3.638-3.996 5.849h3.983v10h-9.983z" />
                    </svg>
                  </div>

                  {/* Quote */}
                  <blockquote className="text-gray-700 mb-6 flex-grow">
                    &quot;{testimonial.quote}&quot;
                  </blockquote>

                  {/* Author */}
                  <div className="flex items-center gap-3 pt-4 border-t border-gray-100">
                    <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center text-primary font-bold text-sm">
                      {testimonial.avatar}
                    </div>
                    <div>
                      <div className="font-semibold text-gray-900">
                        {testimonial.name}
                      </div>
                      <div className="text-sm text-gray-500">
                        {testimonial.role}
                      </div>
                    </div>
                  </div>
                </Card>
              </div>
            ))}
          </div>

          {/* Right arrow */}
          <button
            onClick={() => scroll('right')}
            disabled={!canScrollRight}
            className={`absolute right-0 top-1/2 -translate-y-1/2 translate-x-4 z-10 w-12 h-12 rounded-full bg-white shadow-lg flex items-center justify-center transition-all duration-200 ${
              canScrollRight
                ? 'opacity-100 hover:bg-gray-50 hover:scale-110 cursor-pointer'
                : 'opacity-0 cursor-default'
            }`}
            aria-label="Scroll right"
          >
            <ChevronRight className="w-6 h-6 text-gray-600" />
          </button>
        </div>

        {/* Scroll indicator dots */}
        <div className="flex justify-center gap-2 mt-6">
          {Array.from({ length: Math.ceil(testimonials.length / 3) }).map((_, i) => (
            <div
              key={i}
              className="w-2 h-2 rounded-full bg-gray-300"
            />
          ))}
        </div>

        {/* Note about testimonials */}
        <p className="text-center text-gray-400 text-sm mt-6">
          Join 10,000+ professionals transforming how they work with video
        </p>
      </div>
    </section>
  );
}
