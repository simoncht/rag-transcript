'use client';

import React from 'react';
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
];

export default function TestimonialsSection() {
  return (
    <section className="py-20 bg-gray-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Section header */}
        <div className="text-center mb-16">
          <h2 className="text-4xl font-bold text-gray-900 mb-4">
            Loved by Researchers and Professionals
          </h2>
          <p className="text-xl text-gray-600 max-w-2xl mx-auto">
            See how teams are transforming their video content into searchable knowledge.
          </p>
        </div>

        {/* Testimonial cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          {testimonials.map((testimonial, index) => (
            <Card key={index} className="h-full flex flex-col">
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
          ))}
        </div>

        {/* Note about testimonials */}
        <p className="text-center text-gray-400 text-sm mt-8">
          * Sample testimonials representing typical user experiences
        </p>
      </div>
    </section>
  );
}
