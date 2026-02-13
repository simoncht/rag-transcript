"use client";

import { Button } from "@/components/ui/button";
import {
  ChevronLeft,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { PageSize } from "@/hooks/usePaginationParams";

const PAGE_SIZES: PageSize[] = [10, 20, 50];

interface PaginationBarProps {
  page: number;
  pageSize: number;
  total: number;
  onPageChange: (page: number) => void;
  onPageSizeChange: (size: PageSize) => void;
  isLoading?: boolean;
  /** Label for items, e.g. "conversations", "documents". Defaults to "items". */
  itemLabel?: string;
}

/**
 * Compute which page numbers to display (max 7 slots).
 *
 * Examples:
 *   totalPages=5, current=3  → [1,2,3,4,5]
 *   totalPages=12, current=1 → [1,2,3,"…",12]
 *   totalPages=12, current=6 → [1,"…",5,6,7,"…",12]
 *   totalPages=12, current=12 → [1,"…",10,11,12]
 */
function getPageNumbers(
  current: number,
  totalPages: number
): (number | "…")[] {
  if (totalPages <= 7) {
    return Array.from({ length: totalPages }, (_, i) => i + 1);
  }

  const pages: (number | "…")[] = [];

  // Always include first page
  pages.push(1);

  if (current <= 4) {
    // Near start: 1 2 3 4 5 … last
    pages.push(2, 3, 4, 5, "…", totalPages);
  } else if (current >= totalPages - 3) {
    // Near end: 1 … n-4 n-3 n-2 n-1 n
    pages.push(
      "…",
      totalPages - 4,
      totalPages - 3,
      totalPages - 2,
      totalPages - 1,
      totalPages
    );
  } else {
    // Middle: 1 … c-1 c c+1 … last
    pages.push("…", current - 1, current, current + 1, "…", totalPages);
  }

  return pages;
}

export function PaginationBar({
  page,
  pageSize,
  total,
  onPageChange,
  onPageSizeChange,
  isLoading,
  itemLabel = "items",
}: PaginationBarProps) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const start = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const end = Math.min(page * pageSize, total);

  const pageNumbers = getPageNumbers(page, totalPages);

  return (
    <div
      className="flex flex-col items-center gap-3 px-4 py-3 sm:flex-row sm:justify-between"
      aria-label="Pagination"
    >
      {/* Left: summary */}
      <p className="text-sm text-muted-foreground whitespace-nowrap">
        {total === 0 ? (
          `No ${itemLabel}`
        ) : (
          <>
            Showing{" "}
            <span className="font-medium text-foreground">{start}</span>
            {" - "}
            <span className="font-medium text-foreground">{end}</span>
            {" of "}
            <span className="font-medium text-foreground">{total}</span>
            {` ${itemLabel}`}
          </>
        )}
      </p>

      {/* Center: page size toggle (hidden on mobile) */}
      <div className="hidden sm:flex items-center gap-1" role="group" aria-label="Page size">
        {PAGE_SIZES.map((size) => (
          <button
            key={size}
            onClick={() => onPageSizeChange(size)}
            className={cn(
              "rounded-full px-2.5 py-0.5 text-xs font-medium transition-colors",
              size === pageSize
                ? "bg-primary text-primary-foreground"
                : "bg-muted text-muted-foreground hover:bg-muted/80"
            )}
            aria-label={`Show ${size} per page`}
            aria-pressed={size === pageSize}
          >
            {size}
          </button>
        ))}
      </div>

      {/* Right: page navigation */}
      {totalPages > 1 && (
        <div className="flex items-center gap-1">
          {page > 1 && (
            <>
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8"
                onClick={() => onPageChange(1)}
                disabled={isLoading}
                aria-label="First page"
              >
                <ChevronsLeft className="h-4 w-4" />
              </Button>
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8"
                onClick={() => onPageChange(page - 1)}
                disabled={isLoading}
                aria-label="Previous page"
              >
                <ChevronLeft className="h-4 w-4" />
              </Button>
            </>
          )}

          {pageNumbers.map((item, idx) =>
            item === "…" ? (
              <span
                key={`ellipsis-${idx}`}
                className="px-1 text-sm text-muted-foreground"
                aria-hidden
              >
                …
              </span>
            ) : (
              <Button
                key={item}
                variant={item === page ? "default" : "ghost"}
                size="icon"
                className="h-8 w-8 text-xs"
                onClick={() => onPageChange(item)}
                disabled={isLoading}
                aria-label={`Page ${item}`}
                aria-current={item === page ? "page" : undefined}
              >
                {item}
              </Button>
            )
          )}

          {page < totalPages && (
            <>
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8"
                onClick={() => onPageChange(page + 1)}
                disabled={isLoading}
                aria-label="Next page"
              >
                <ChevronRight className="h-4 w-4" />
              </Button>
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8"
                onClick={() => onPageChange(totalPages)}
                disabled={isLoading}
                aria-label="Last page"
              >
                <ChevronsRight className="h-4 w-4" />
              </Button>
            </>
          )}
        </div>
      )}
    </div>
  );
}
