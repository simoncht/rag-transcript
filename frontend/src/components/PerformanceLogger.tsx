"use client";

import { useEffect, useRef } from "react";
import { usePathname } from "next/navigation";

/**
 * Performance Logger Component
 *
 * Logs navigation timing to console to identify bottlenecks
 */
export function PerformanceLogger() {
  const pathname = usePathname();
  const startTimeRef = useRef<number>(Date.now());
  const renderCountRef = useRef(0);

  useEffect(() => {
    renderCountRef.current++;
    const now = Date.now();
    const timeSinceStart = now - startTimeRef.current;

    console.log(`[Performance] Render #${renderCountRef.current} at ${pathname}`, {
      timeSinceNavigationStart: `${timeSinceStart}ms`,
      timestamp: new Date().toISOString(),
    });
  });

  useEffect(() => {
    // Reset on pathname change
    startTimeRef.current = Date.now();
    renderCountRef.current = 0;
    console.log(`[Performance] Navigation started to ${pathname}`);

    // Log when page is interactive
    const timer = setTimeout(() => {
      console.log(`[Performance] Page interactive at ${pathname}`, {
        totalTime: `${Date.now() - startTimeRef.current}ms`,
      });
    }, 0);

    return () => clearTimeout(timer);
  }, [pathname]);

  return null;
}
