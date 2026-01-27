/**
 * Auth Module - Public API
 *
 * Exports auth abstractions following SOLID principles.
 * Components import from this module, not from Clerk directly.
 */

// Types & Interfaces (ISP - Interface Segregation)
export type { AuthState, AuthUser, IAuthProvider, ParallelResult } from "./types";

// Context & Hooks (DI - Dependency Injection)
export { AuthProvider, useAuth, useAuthState } from "./AuthContext";

// Adapter (DIP - Dependency Inversion)
export { NextAuthAdapter } from "./NextAuthAdapter";

// Utilities (SRP - Single Responsibility)
export { prefetchParallel, createParallelQueryFn } from "./parallelFetcher";
