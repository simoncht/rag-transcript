'use client';

import React from 'react';

type BadgeVariant = 'success' | 'warning' | 'error' | 'info' | 'default';

interface BadgeProps {
  variant?: BadgeVariant;
  children: React.ReactNode;
  className?: string;
}

/**
 * Badge - Status indicator component
 * Semantic color variants
 */
export default function Badge({
  variant = 'default',
  children,
  className = '',
}: BadgeProps) {
  const variantStyles = {
    success: 'bg-green-50 text-green-800 border-green-200',
    warning: 'bg-yellow-50 text-yellow-800 border-yellow-200',
    error: 'bg-red-50 text-red-800 border-red-200',
    info: 'bg-blue-50 text-blue-800 border-blue-200',
    default: 'bg-primary-50 text-primary-dark border-primary-100',
  };

  // Map semantic variants to theme colors
  const semanticStyles = {
    success: 'bg-opacity-10 text-color-success border-color-success',
    warning: 'bg-secondary bg-opacity-10 text-secondary-dark border-secondary-light',
    error: 'bg-red-100 text-red-800 border-red-200',
    info: 'bg-primary-50 text-primary-dark border-primary-100',
    default: 'bg-primary-50 text-primary-dark border-primary-100',
  };

  return (
    <span
      className={`
        inline-block
        px-3 py-1
        rounded-full
        border
        text-xs font-medium
        ${variantStyles[variant]}
        ${className}
      `}
    >
      {children}
    </span>
  );
}
