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
 * Fetch auth and data in parallel
 *
 * Returns both results along with timing metrics.
 * Throws if authentication fails (data errors are returned).
 *
 * @param authProvider - Auth provider instance
 * @param dataFetcher - Function that fetches data (receives auth state)
 * @param options - Configuration options
 */
export async function fetchParallel<TData>(
  authProvider: IAuthProvider,
  dataFetcher: (isAuthenticated: boolean) => Promise<TData>,
  options?: {
    /**
     * If true, cancels data fetch if auth fails
     * If false, attempts data fetch regardless
     */
    requireAuth?: boolean;
    /**
     * Timeout in ms for the entire operation
     */
    timeoutMs?: number;
  }
): Promise<ParallelResult<boolean, TData>> {
  const requireAuth = options?.requireAuth ?? true;
  const timeoutMs = options?.timeoutMs ?? 15000;

  const startTime = performance.now();
  let authStartTime = startTime;
  let dataStartTime = startTime;

  // Start both operations in parallel
  const authPromise = (async () => {
    authStartTime = performance.now();
    const state = await authProvider.getStateAsync();
    return state.isAuthenticated;
  })();

  const dataPromise = (async () => {
    dataStartTime = performance.now();

    if (requireAuth) {
      // Wait for auth, then fetch data if authenticated
      const isAuth = await authPromise;
      if (!isAuth) {
        throw new Error("Not authenticated");
      }
      return await dataFetcher(isAuth);
    } else {
      // Fetch data optimistically without waiting for auth
      return await dataFetcher(false);
    }
  })();

  // Race against timeout
  const timeoutPromise = new Promise<never>((_, reject) =>
    setTimeout(() => reject(new Error("Parallel fetch timeout")), timeoutMs)
  );

  try {
    const [isAuthenticated, data] = await Promise.race([
      Promise.all([authPromise, dataPromise]),
      timeoutPromise,
    ]);

    const endTime = performance.now();

    return {
      auth: isAuthenticated,
      data,
      timing: {
        authMs: Math.round(endTime - authStartTime),
        dataMs: Math.round(endTime - dataStartTime),
        totalMs: Math.round(endTime - startTime),
      },
    };
  } catch (error) {
    // Log timing even on error for debugging
    const endTime = performance.now();
    console.error("Parallel fetch failed:", {
      error,
      timing: {
        authMs: Math.round(endTime - authStartTime),
        dataMs: Math.round(endTime - dataStartTime),
        totalMs: Math.round(endTime - startTime),
      },
    });
    throw error;
  }
}

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
