/**
 * Auth Abstraction Layer - Interface Segregation Principle
 *
 * Minimal interfaces for auth functionality to avoid coupling to Clerk specifics.
 * Components depend on these abstractions, not concrete implementations.
 */

/**
 * Minimal auth state required by UI components
 */
export interface AuthState {
  isAuthenticated: boolean;
  user: AuthUser | null;
  token: string | null;
}

/**
 * User information abstracted from auth provider
 */
export interface AuthUser {
  id: string;
  email: string;
  displayName?: string;
  metadata?: Record<string, unknown>;
}

/**
 * Auth provider interface - Single Responsibility
 *
 * Responsibility: Manage authentication state and provide user info
 */
export interface IAuthProvider {
  /**
   * Get current auth state synchronously (may be stale)
   * Returns immediately without blocking
   */
  getState(): AuthState;

  /**
   * Get current auth state with fresh data
   * Returns promise that resolves when auth is confirmed
   */
  getStateAsync(): Promise<AuthState>;

  /**
   * Get auth token for API requests
   */
  getToken(): Promise<string | null>;

  /**
   * Sign out current user
   */
  signOut(redirectUrl?: string): Promise<void>;

  /**
   * Subscribe to auth state changes
   */
  subscribe(listener: (state: AuthState) => void): () => void;
}

/**
 * Result type for parallel operations
 */
export type ParallelResult<TAuth, TData> = {
  auth: TAuth;
  data: TData;
  timing: {
    authMs: number;
    dataMs: number;
    totalMs: number;
  };
};
