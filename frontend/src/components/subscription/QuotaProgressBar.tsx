'use client';

import React from 'react';

interface QuotaProgressBarProps {
  used: number;
  limit: number;
  label: string;
  showDetails?: boolean;
  className?: string;
}

/**
 * QuotaProgressBar - Progress bar with label and percentage
 * Shows "Unlimited" for -1 limits
 */
export default function QuotaProgressBar({
  used,
  limit,
  label,
  showDetails = true,
  className = '',
}: QuotaProgressBarProps) {
  const isUnlimited = limit === -1;
  const percentage = isUnlimited ? 0 : Math.min((used / limit) * 100, 100);

  // Determine color based on usage
  const getBarColorClass = () => {
    if (isUnlimited) return 'bg-green-500';
    if (percentage >= 90) return 'bg-red-500';
    if (percentage >= 70) return 'bg-yellow-500';
    return 'bg-green-500';
  };

  return (
    <div className={`space-y-2 ${className}`}>
      {/* Label and usage */}
      <div className="flex items-center justify-between text-sm">
        <span className="font-medium text-gray-700">{label}</span>
        {showDetails && (
          <span className="text-gray-500">
            {isUnlimited ? (
              <span className="text-green-600 font-medium">Unlimited</span>
            ) : (
              <>
                {used.toLocaleString()} / {limit.toLocaleString()}
                {' '}
                <span className="text-gray-400">
                  ({Math.round(percentage)}%)
                </span>
              </>
            )}
          </span>
        )}
      </div>

      {/* Progress bar */}
      <div className="w-full bg-gray-200 rounded-full h-2.5 overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-300 ${getBarColorClass()}`}
          style={{
            width: isUnlimited ? '100%' : `${percentage}%`,
          }}
        />
      </div>
    </div>
  );
}
