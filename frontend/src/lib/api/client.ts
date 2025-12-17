import axios from "axios";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const API_V1_PREFIX = process.env.NEXT_PUBLIC_API_V1_PREFIX || "/api/v1";

type TokenGetter = () => Promise<string | null>;

let clerkTokenGetter: TokenGetter | null = null;

export function setClerkTokenGetter(getter: TokenGetter | null) {
  clerkTokenGetter = getter;
}

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

  if (clerkTokenGetter) {
    try {
      const token = await clerkTokenGetter();
      if (token) {
        if (!config.headers) {
          config.headers = {} as any;
        }
        (config.headers as any).Authorization = `Bearer ${token}`;
      }
    } catch {
      // If token retrieval fails, proceed without Authorization header.
    }
  }

  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    // Let Clerk's middleware and components handle auth redirects.
    // Avoid forcing a client-side redirect here to prevent navigation loops.
    return Promise.reject(error);
  }
);
