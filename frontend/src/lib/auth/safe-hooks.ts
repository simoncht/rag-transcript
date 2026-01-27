/**
 * Safe Auth Hooks - Handle cases when AuthProvider isn't available
 *
 * These hooks provide graceful fallbacks for public pages where
 * AuthProvider may not be rendered (e.g., when Clerk isn't configured)
 */

"use client";

import { useContext, useState, useEffect } from "react";
import { AuthContext } from "./AuthContext";
import type { AuthState } from "./types";

const defaultAuthState: AuthState = {
  isAuthenticated: false,
  isLoading: false,
  user: null,
  token: null,
};

/**
 * Safe version of useAuthState that doesn't throw when AuthProvider is missing
 *
 * Returns default unauthenticated state if AuthProvider isn't available.
 * Use this in components that may be rendered on public pages.
 */
export function useSafeAuthState(): AuthState {
  const context = useContext(AuthContext);

  const [state, setState] = useState<AuthState>(() => {
    if (!context) {
      return defaultAuthState;
    }
    return context.getState();
  });

  useEffect(() => {
    if (!context) {
      return;
    }

    // Subscribe to changes
    const unsubscribe = context.subscribe(setState);
    setState(context.getState()); // Sync immediately

    return unsubscribe;
  }, [context]);

  return state;
}
