import axios from "axios";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const API_V1_PREFIX = process.env.NEXT_PUBLIC_API_V1_PREFIX || "/api/v1";

type TokenGetter = () => Promise<string | null>;

let authTokenGetter: TokenGetter | null = null;

// Performance: Token caching to avoid repeated async fetches
// Clerk tokens are valid for ~60s, so we cache for 50s to be safe
const TOKEN_CACHE_TTL_MS = 50 * 1000; // 50 seconds
let cachedToken: string | null = null;
let tokenCacheTimestamp: number = 0;
let tokenFetchPromise: Promise<string | null> | null = null;

async function getCachedToken(): Promise<string | null> {
  const now = Date.now();

  // Return cached token if still valid
  if (cachedToken && (now - tokenCacheTimestamp) < TOKEN_CACHE_TTL_MS) {
    return cachedToken;
  }

  // If a fetch is already in progress, wait for it (deduplication)
  if (tokenFetchPromise) {
    return tokenFetchPromise;
  }

  // Fetch new token
  if (!authTokenGetter) {
    return null;
  }

  tokenFetchPromise = (async () => {
    try {
      const token = await authTokenGetter!();
      cachedToken = token;
      tokenCacheTimestamp = Date.now();
      return token;
    } catch {
      return null;
    } finally {
      tokenFetchPromise = null;
    }
  })();

  return tokenFetchPromise;
}

export function setAuthTokenGetter(getter: TokenGetter | null) {
  authTokenGetter = getter;
  // Clear cache when getter changes (e.g., on logout)
  cachedToken = null;
  tokenCacheTimestamp = 0;
}

// Export for testing/debugging
export function clearTokenCache() {
  cachedToken = null;
  tokenCacheTimestamp = 0;
  tokenFetchPromise = null;
}

// Export getCachedToken for streaming client (which uses fetch instead of axios)
export { getCachedToken };

export const apiClient = axios.create({
  baseURL: `${API_BASE_URL}${API_V1_PREFIX}`,
  headers: {
    "Content-Type": "application/json",
  },
});

apiClient.interceptors.request.use(async (config) => {
  // Only attempt to attach a token in browser environments.
  if (typeof window === "undefined") {
    return config;
  }

  // Performance: Use cached token instead of fetching on every request
  const token = await getCachedToken();
  if (token) {
    if (!config.headers) {
      config.headers = {} as any;
    }
    (config.headers as any).Authorization = `Bearer ${token}`;
  }

  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    // On 401, clear cached token so next request gets a fresh one
    if (error.response?.status === 401) {
      clearTokenCache();
    }
    return Promise.reject(error);
  }
);
