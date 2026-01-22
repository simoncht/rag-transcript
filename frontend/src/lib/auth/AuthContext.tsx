/**
 * Auth Context - Dependency Injection Pattern
 *
 * Provides IAuthProvider to components via React Context.
 * Components use useAuth() hook instead of NextAuth hooks directly.
 *
 * Benefits:
 * - Decouples components from NextAuth
 * - Enables parallel auth + data fetching
 * - Testable with mock providers
 * - Follows Dependency Inversion Principle
 */

"use client";

import { createContext, useContext, useEffect, useState, useRef } from "react";
import { useSession } from "next-auth/react";
import { NextAuthAdapter } from "./NextAuthAdapter";
import type { IAuthProvider, AuthState } from "./types";

export const AuthContext = createContext<IAuthProvider | null>(null);

/**
 * Auth Provider Component
 *
 * Single Responsibility: Provide auth state to component tree
 */
export function AuthProvider({ children }: { children: React.ReactNode }) {
  const { data: session, status } = useSession();

  // Create adapter once and reuse (avoid re-creating on every render)
  const adapterRef = useRef<NextAuthAdapter | null>(null);
  if (!adapterRef.current) {
    adapterRef.current = new NextAuthAdapter(session);
  }

  const adapter = adapterRef.current;
  // Keep adapter references in sync with the latest session
  adapter.updateSession(session);

  // Update adapter when NextAuth session changes
  useEffect(() => {
    adapter.notifyStateChange();
  }, [adapter, session, status]);

  // Local state for triggering re-renders
  const [authState, setAuthState] = useState<AuthState>(() => adapter.getState());

  // Subscribe to adapter changes
  useEffect(() => {
    const unsubscribe = adapter.subscribe(setAuthState);
    return unsubscribe;
  }, [adapter]);

  return <AuthContext.Provider value={adapter}>{children}</AuthContext.Provider>;
}

/**
 * Hook to access auth provider
 *
 * Returns IAuthProvider interface, not NextAuth-specific types
 */
export function useAuth(): IAuthProvider {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
}

/**
 * Hook to get current auth state (synchronous)
 *
 * Returns cached state immediately without blocking.
 * Subscribe to changes via useEffect.
 */
export function useAuthState(): AuthState {
  const provider = useAuth();
  const [state, setState] = useState<AuthState>(() => provider.getState());

  useEffect(() => {
    // Update state when provider changes
    const unsubscribe = provider.subscribe(setState);
    setState(provider.getState()); // Sync immediately
    return unsubscribe;
  }, [provider]);

  return state;
}

/**
 * Hook for async auth state (use with Suspense)
 *
 * Suspends until auth is loaded, then returns state.
 * Enables parallel rendering with React Suspense.
 */
export function useAuthStateAsync(): AuthState {
  const provider = useAuth();
  const [state, setState] = useState<AuthState | null>(null);
  const [promise, setPromise] = useState<Promise<AuthState> | null>(null);

  useEffect(() => {
    let cancelled = false;

    const fetchAuth = async () => {
      try {
        const authState = await provider.getStateAsync();
        if (!cancelled) {
          setState(authState);
        }
      } catch (error) {
        console.error("Auth fetch failed:", error);
      }
    };

    // Create promise for Suspense
    const authPromise = fetchAuth();
    setPromise(authPromise as any);

    return () => {
      cancelled = true;
    };
  }, [provider]);

  if (!state && promise) {
    throw promise; // Suspend until auth loads
  }

  return state ?? provider.getState();
}
