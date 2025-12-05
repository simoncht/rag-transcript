'use client';

import React from 'react';

type ButtonVariant = 'primary' | 'secondary' | 'accent' | 'outline' | 'ghost';
type ButtonSize = 'sm' | 'base' | 'lg';

interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  isLoading?: boolean;
  children: React.ReactNode;
}

/**
 * Button - Theme-aware button component
 * Supports multiple variants and sizes
 */
export default function Button({
  variant = 'primary',
  size = 'base',
  isLoading = false,
  children,
  disabled,
  className = '',
  ...props
}: ButtonProps) {
  // Base styles
  const baseStyles = 'font-medium rounded-lg transition-all duration-200 ease-smooth focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed';

  // Variant styles
  const variantStyles = {
    primary: 'bg-primary text-bg-primary hover:bg-primary-light active:bg-primary-dark focus-visible:ring-primary',
    secondary: 'bg-secondary text-bg-primary hover:bg-secondary-light active:bg-secondary-dark focus-visible:ring-secondary',
    accent: 'bg-accent-main text-bg-primary hover:bg-accent-light active:bg-accent-dark focus-visible:ring-accent-main',
    outline: 'border-2 border-primary text-primary hover:bg-primary-50 active:bg-primary-100 focus-visible:ring-primary',
    ghost: 'text-primary hover:bg-primary-50 active:bg-primary-100 focus-visible:ring-primary',
  };

  // Size styles
  const sizeStyles = {
    sm: 'px-3 py-1.5 text-sm',
    base: 'px-4 py-2 text-base',
    lg: 'px-6 py-3 text-lg',
  };

  return (
    <button
      disabled={disabled || isLoading}
      className={`
        ${baseStyles}
        ${variantStyles[variant]}
        ${sizeStyles[size]}
        ${className}
      `}
      {...props}
    >
      <span className="flex items-center justify-center gap-2">
        {isLoading && (
          <svg
            className="w-4 h-4 animate-spin"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
          >
            <circle
              className="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              strokeWidth="4"
            />
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
            />
          </svg>
        )}
        {children}
      </span>
    </button>
  );
}
