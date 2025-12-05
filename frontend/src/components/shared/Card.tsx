'use client';

import React from 'react';

interface CardProps {
  children: React.ReactNode;
  className?: string;
  isPressable?: boolean;
  onClick?: () => void;
  hoverable?: boolean;
}

/**
 * Card - Theme-aware container component
 * Soft shadows, elegant borders, perfect for information cards
 */
export default function Card({
  children,
  className = '',
  isPressable = false,
  onClick,
  hoverable = true,
}: CardProps) {
  return (
    <div
      className={`
        bg-bg-secondary
        border border-border-default
        rounded-lg
        p-6
        shadow-sm
        transition-all duration-200 ease-smooth
        ${hoverable && 'hover:shadow-md hover:border-border-hover'}
        ${isPressable && 'cursor-pointer'}
        ${className}
      `}
      onClick={onClick}
      role={isPressable ? 'button' : undefined}
      tabIndex={isPressable ? 0 : undefined}
      onKeyDown={isPressable ? (e) => {
        if (e.key === 'Enter' || e.key === ' ') onClick?.();
      } : undefined}
    >
      {children}
    </div>
  );
}
