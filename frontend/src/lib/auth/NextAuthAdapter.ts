/**
 * NextAuth Adapter - Dependency Inversion Principle
 *
 * Adapts NextAuth.js to our IAuthProvider interface.
 * Components depend on IAuthProvider abstraction, not NextAuth directly.
 *
 * Benefits:
 * - Clean migration from Clerk
 * - Testable with mock implementations
 * - No NextAuth imports needed in components
 */

import { signIn, signOut } from "next-auth/react"
import type { AuthState, AuthUser, IAuthProvider } from "./types"

// Minimal NextAuth types we depend on
type NextAuthSession = {
  user?: {
    id?: string
    email?: string | null
    name?: string | null
    image?: string | null
  } | null
  expires?: string
} | null

/**
 * NextAuth-specific implementation of IAuthProvider
 *
 * Wraps NextAuth session and provides a consistent interface.
 * Performance: Returns cached state synchronously, fetches fresh data async.
 */
export class NextAuthAdapter implements IAuthProvider {
  private cachedState: AuthState
  private listeners: Set<(state: AuthState) => void> = new Set()
  private session: NextAuthSession

  constructor(session: NextAuthSession) {
    this.session = session
    this.cachedState = this.buildState()
  }

  /**
   * Update session reference when it changes (prevents stale auth state)
   */
  updateSession(session: NextAuthSession): void {
    this.session = session
    this.notifyStateChange()
  }

  /**
   * Get auth state immediately without blocking
   *
   * Returns cached state which is updated by subscribe() callbacks.
   * Use for non-critical UI that tolerates eventual consistency.
   */
  getState(): AuthState {
    return this.cachedState
  }

  /**
   * Get fresh auth state with promise
   *
   * NextAuth loads synchronously on server, so this returns immediately.
   * Use when you need guaranteed fresh data.
   */
  async getStateAsync(): Promise<AuthState> {
    const state = this.buildState()
    this.updateCache(state)
    return state
  }

  /**
   * Get auth token for API requests
   *
   * NextAuth manages tokens internally via httpOnly cookies.
   * For backend API calls, we fetch the JWT from our token endpoint.
   * Note: We always try to fetch the token, even if session isn't loaded in React yet,
   * because the httpOnly cookie may exist even when useSession() hasn't resolved.
   */
  async getToken(): Promise<string | null> {
    try {
      const response = await fetch("/api/auth/token")
      if (!response.ok) return null
      const data = await response.json()
      return data.token || null
    } catch {
      return null
    }
  }

  /**
   * Sign in with OAuth provider
   */
  async signIn(redirectUrl?: string): Promise<void> {
    await signIn("google", { callbackUrl: redirectUrl || "/videos" })
  }

  /**
   * Sign out user
   */
  async signOut(redirectUrl?: string): Promise<void> {
    await signOut({ callbackUrl: redirectUrl || "/" })
  }

  /**
   * Subscribe to auth state changes
   *
   * Returns unsubscribe function
   */
  subscribe(listener: (state: AuthState) => void): () => void {
    this.listeners.add(listener)
    return () => {
      this.listeners.delete(listener)
    }
  }

  /**
   * Update cached state when session changes
   *
   * Call this from React effects when NextAuth session updates
   */
  notifyStateChange(): void {
    const newState = this.buildState()
    if (this.stateChanged(this.cachedState, newState)) {
      this.updateCache(newState)
    }
  }

  /**
   * Build AuthState from current NextAuth session
   */
  private buildState(): AuthState {
    const sessionUser = this.session?.user

    if (!sessionUser || !sessionUser.email) {
      return {
        isAuthenticated: false,
        user: null,
        token: null,
      }
    }

    const user: AuthUser = {
      id: sessionUser.email, // Use email as stable ID
      email: sessionUser.email,
      displayName: sessionUser.name || sessionUser.email,
      metadata: {
        provider: "google",
        image: sessionUser.image,
      },
    }

    return {
      isAuthenticated: true,
      user,
      token: null, // Token fetched on-demand via getToken()
    }
  }

  /**
   * Update cache and notify listeners
   */
  private updateCache(state: AuthState): void {
    this.cachedState = state
    this.listeners.forEach((listener) => listener(state))
  }

  /**
   * Check if state actually changed (avoid unnecessary updates)
   */
  private stateChanged(old: AuthState, next: AuthState): boolean {
    return (
      old.isAuthenticated !== next.isAuthenticated ||
      old.user?.id !== next.user?.id ||
      old.user?.email !== next.user?.email
    )
  }
}
