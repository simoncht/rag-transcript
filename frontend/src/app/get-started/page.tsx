'use client';

import { Suspense } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';

// Icons for the 3-step flow
const LinkIcon = () => (
  <svg
    className="w-8 h-8"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.75"
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
    <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
  </svg>
);

const SparklesIcon = () => (
  <svg
    className="w-8 h-8"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.75"
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    <path d="M12 5a3 3 0 1 0-5.997.125 4 4 0 0 0-2.526 5.77 4 4 0 0 0 .556 6.588A4 4 0 1 0 12 18Z" />
    <path d="M12 5a3 3 0 1 1 5.997.125 4 4 0 0 1 2.526 5.77 4 4 0 0 1-.556 6.588A4 4 0 1 1 12 18Z" />
    <path d="M15 13a4.5 4.5 0 0 1-3-4 4.5 4.5 0 0 1-3 4" />
    <path d="M12 18v4" />
  </svg>
);

const MessageIcon = () => (
  <svg
    className="w-8 h-8"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.75"
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    <path d="M7.9 20A9 9 0 1 0 4 16.1L2 22Z" />
    <path d="M8 12h.01" />
    <path d="M12 12h.01" />
    <path d="M16 12h.01" />
  </svg>
);

const CheckIcon = () => (
  <svg
    className="w-5 h-5 text-[var(--color-primary)]"
    fill="none"
    strokeLinecap="round"
    strokeLinejoin="round"
    strokeWidth="2.5"
    viewBox="0 0 24 24"
    stroke="currentColor"
  >
    <path d="M5 13l4 4L19 7" />
  </svg>
);

const GoogleIcon = () => (
  <svg className="w-5 h-5" viewBox="0 0 24 24">
    <path
      fill="#4285F4"
      d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
    />
    <path
      fill="#34A853"
      d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
    />
    <path
      fill="#FBBC05"
      d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
    />
    <path
      fill="#EA4335"
      d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
    />
  </svg>
);

const steps = [
  {
    number: 1,
    icon: <LinkIcon />,
    title: 'Add your content',
    description: 'Video link or document',
  },
  {
    number: 2,
    icon: <SparklesIcon />,
    title: 'AI transcribes',
    description: 'Instant, accurate text',
  },
  {
    number: 3,
    icon: <MessageIcon />,
    title: 'Ask anything',
    description: 'Get cited answers, every time',
  },
];

const freeTierBenefits = [
  '10 videos to start',
  '200 messages per month',
  '1 GB storage',
  'AI-powered search & chat',
];

function GetStartedContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const callbackUrl = searchParams.get('callbackUrl') || '/videos';

  const handleGoogleSignIn = () => {
    router.push(`/sign-in?callbackUrl=${encodeURIComponent(callbackUrl)}`);
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-[var(--color-bg-secondary)] to-white flex flex-col">
      {/* Header */}
      <header className="w-full py-6 px-4 sm:px-6 lg:px-8">
        <div className="max-w-4xl mx-auto flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2 group">
            <div className="w-8 h-8 bg-gradient-to-br from-[var(--color-primary)] to-[var(--color-primary-dark)] rounded-lg flex items-center justify-center">
              <svg
                className="w-5 h-5 text-white"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={2}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"
                />
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                />
              </svg>
            </div>
            <span className="text-lg font-semibold text-[var(--color-text-primary)] group-hover:text-[var(--color-primary)] transition-colors">
              RAG Transcript
            </span>
          </Link>
          <Link
            href="/login"
            className="text-sm text-[var(--color-text-secondary)] hover:text-[var(--color-primary)] transition-colors"
          >
            Already have an account? <span className="font-medium">Sign in</span>
          </Link>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 flex items-center justify-center px-4 sm:px-6 lg:px-8 py-8">
        <div className="w-full max-w-2xl">
          {/* Headline */}
          <div className="text-center mb-10">
            <h1 className="text-3xl sm:text-4xl font-bold text-[var(--color-text-primary)] mb-3">
              The Answer Is in There Somewhere.
              <br />
              <span className="text-[var(--color-primary)]">Find It in Seconds.</span>
            </h1>
          </div>

          {/* 3-Step Flow */}
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4 sm:gap-2 mb-10">
            {steps.map((step, index) => (
              <div key={step.number} className="flex items-center">
                {/* Step Card */}
                <div className="flex flex-col items-center text-center w-40">
                  <div className="w-16 h-16 rounded-2xl bg-[var(--color-primary)]/10 flex items-center justify-center mb-3 text-[var(--color-primary)] border border-[var(--color-primary)]/20">
                    {step.icon}
                  </div>
                  <div className="text-sm font-medium text-[var(--color-text-secondary)] mb-1">
                    Step {step.number}
                  </div>
                  <div className="font-semibold text-[var(--color-text-primary)]">
                    {step.title}
                  </div>
                  <div className="text-sm text-[var(--color-text-secondary)]">
                    {step.description}
                  </div>
                </div>

                {/* Arrow connector (not after last step) */}
                {index < steps.length - 1 && (
                  <div className="hidden sm:block mx-2">
                    <svg
                      viewBox="0 0 24 24"
                      className="w-6 h-6 text-[var(--color-primary)]/50"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2.5"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    >
                      <path d="M9 18l6-6-6-6" />
                    </svg>
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* Free Tier Card */}
          <div className="bg-white rounded-2xl border border-[var(--color-border)] shadow-sm p-6 mb-8">
            <h2 className="text-lg font-semibold text-[var(--color-text-primary)] mb-4 text-center">
              What you get — no credit card, no catch
            </h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {freeTierBenefits.map((benefit) => (
                <div key={benefit} className="flex items-center gap-3">
                  <CheckIcon />
                  <span className="text-[var(--color-text-secondary)]">{benefit}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Google Sign In Button */}
          <div className="space-y-4">
            {/* No credit card badge - prominent trust signal above CTA */}
            <div className="flex items-center justify-center gap-2 text-[var(--color-primary)]">
              <svg
                className="w-5 h-5"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth="2"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z"
                />
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M4 4l16 16"
                />
              </svg>
              <span className="font-medium">No credit card required</span>
            </div>

            <button
              onClick={handleGoogleSignIn}
              className="w-full flex items-center justify-center gap-3 bg-white border-2 border-[var(--color-border)] rounded-xl px-6 py-4 font-semibold text-[var(--color-text-primary)] hover:bg-[var(--color-bg-secondary)] hover:border-[var(--color-primary)]/30 transition-all shadow-sm"
            >
              <GoogleIcon />
              Continue with Google
            </button>

            {/* Legal text */}
            <p className="text-center text-sm text-[var(--color-text-secondary)]">
              By continuing, you agree to our{' '}
              <Link
                href="/terms"
                className="text-[var(--color-primary)] hover:underline"
              >
                Terms of Service
              </Link>{' '}
              and{' '}
              <Link
                href="/privacy"
                className="text-[var(--color-primary)] hover:underline"
              >
                Privacy Policy
              </Link>
            </p>
          </div>
        </div>
      </main>
    </div>
  );
}

function GetStartedFallback() {
  return (
    <div className="min-h-screen bg-gradient-to-b from-[var(--color-bg-secondary)] to-white flex items-center justify-center">
      <div className="w-full max-w-2xl px-4">
        <div className="text-center">
          <div className="w-8 h-8 bg-[var(--color-primary)]/20 rounded-lg mx-auto mb-4 animate-pulse" />
          <div className="h-8 bg-gray-200 rounded w-3/4 mx-auto mb-4 animate-pulse" />
          <div className="h-4 bg-gray-200 rounded w-1/2 mx-auto animate-pulse" />
        </div>
      </div>
    </div>
  );
}

export default function GetStartedPage() {
  return (
    <Suspense fallback={<GetStartedFallback />}>
      <GetStartedContent />
    </Suspense>
  );
}
