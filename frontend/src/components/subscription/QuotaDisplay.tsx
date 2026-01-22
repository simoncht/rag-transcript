'use client';

import React from 'react';

type QuotaVariant = 'compact' | 'full';

interface QuotaDisplayProps {
  used: number;
  limit: number;
  label: string;
  variant?: QuotaVariant;
  className?: string;
}

/**
 * QuotaDisplay - Small indicator showing quota status (e.g., "2/2 videos")
 * Color-coded: green (<70%), yellow (70-90%), red (>90%)
 */
export default function QuotaDisplay({
  used,
  limit,
  label,
  variant = 'compact',
  className = '',
}: QuotaDisplayProps) {
  // Handle unlimited quotas (-1)
  const isUnlimited = limit === -1;
  const percentage = isUnlimited ? 0 : (used / limit) * 100;

  // Determine color based on usage
  const getColorClass = () => {
    if (isUnlimited) return 'text-green-600';
    if (percentage >= 90) return 'text-red-600';
    if (percentage >= 70) return 'text-yellow-600';
    return 'text-green-600';
  };

  const getBgColorClass = () => {
    if (isUnlimited) return 'bg-green-50 border-green-200';
    if (percentage >= 90) return 'bg-red-50 border-red-200';
    if (percentage >= 70) return 'bg-yellow-50 border-yellow-200';
    return 'bg-green-50 border-green-200';
  };

  if (variant === 'compact') {
    return (
      <span
        className={`inline-flex items-center gap-1 text-sm ${getColorClass()} ${className}`}
      >
        <span className="font-medium">
          {isUnlimited ? '∞' : `${used}/${limit}`}
        </span>
        <span className="text-gray-500">{label}</span>
      </span>
    );
  }

  // Full variant with badge styling
  return (
    <span
      className={`
        inline-flex items-center gap-2
        px-3 py-1.5
        rounded-lg
        border
        text-sm font-medium
        ${getBgColorClass()}
        ${getColorClass()}
        ${className}
      `}
    >
      <span className="font-semibold">
        {isUnlimited ? 'Unlimited' : `${used}/${limit}`}
      </span>
      <span className="text-gray-600">{label}</span>
    </span>
  );
}
