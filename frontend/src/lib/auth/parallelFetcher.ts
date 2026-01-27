/**
 * Parallel Fetcher - Single Responsibility Principle
 *
 * Responsibility: Coordinate parallel auth + data fetching
 *
 * Performance Benefits:
 * - Auth and data fetch start simultaneously (not sequential)
 * - Total time = max(authTime, dataTime) instead of authTime + dataTime
 * - Expected improvement: 5s → 1-2s for collections page
 */

import type { IAuthProvider, ParallelResult } from "./types";

/**
 * Prefetch data before auth completes (optimistic)
 *
 * Starts data fetch immediately without waiting for auth.
 * Useful for public data or when initial loading states are acceptable.
 *
 * Returns a promise that resolves when both complete.
 */
export async function prefetchParallel<TData>(
  authProvider: IAuthProvider,
  dataFetcher: () => Promise<TData>
): Promise<ParallelResult<boolean, TData>> {
  const startTime = performance.now();

  // Fire both simultaneously
  const [authResult, dataResult] = await Promise.allSettled([
    authProvider.getStateAsync(),
    dataFetcher(),
  ]);

  const endTime = performance.now();

  if (authResult.status === "rejected") {
    throw new Error(`Auth failed: ${authResult.reason}`);
  }

  if (dataResult.status === "rejected") {
    throw new Error(`Data fetch failed: ${dataResult.reason}`);
  }

  return {
    auth: authResult.value.isAuthenticated,
    data: dataResult.value,
    timing: {
      authMs: Math.round(endTime - startTime),
      dataMs: Math.round(endTime - startTime),
      totalMs: Math.round(endTime - startTime),
    },
  };
}

/**
 * Create a memoized parallel fetcher for React Query
 *
 * Returns a query function that fetches auth + data in parallel.
 * Use with React Query's queryFn parameter.
 */
export function createParallelQueryFn<TData>(
  authProvider: IAuthProvider,
  dataFetcher: () => Promise<TData>
) {
  return async (): Promise<TData> => {
    const result = await prefetchParallel(authProvider, dataFetcher);

    // Log performance metrics in development
    if (process.env.NODE_ENV === "development") {
      console.log("[ParallelFetch]", {
        authenticated: result.auth,
        timing: result.timing,
      });
    }

    return result.data;
  };
}
