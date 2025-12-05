/**
 * Spacing and Component System
 * Consistent spacing, shadows, and border radius for harmony
 */

export const mindfulLearningSpacing = {
  // Spacing scale (based on 4px unit)
  spacing: {
    0: '0',
    1: '0.25rem',       // 4px
    2: '0.5rem',        // 8px
    3: '0.75rem',       // 12px
    4: '1rem',          // 16px
    5: '1.25rem',       // 20px
    6: '1.5rem',        // 24px
    7: '1.75rem',       // 28px
    8: '2rem',          // 32px
    9: '2.25rem',       // 36px
    10: '2.5rem',       // 40px
    12: '3rem',         // 48px
    16: '4rem',         // 64px
    20: '5rem',         // 80px
  },

  // Border radius
  borderRadius: {
    none: '0',
    sm: '0.375rem',     // 6px - small interactive elements
    base: '0.5rem',     // 8px - default components
    md: '0.75rem',      // 12px - cards and containers
    lg: '1rem',         // 16px - larger components
    xl: '1.5rem',       // 24px - very large elements
    full: '9999px',     // full rounded (for pills)
  },

  // Shadows - soft, subtle, no harsh effects
  shadows: {
    none: 'none',
    sm: '0 1px 2px 0 rgba(44, 62, 63, 0.05)',
    base: '0 2px 8px 0 rgba(44, 62, 63, 0.08)',
    md: '0 4px 12px 0 rgba(44, 62, 63, 0.1)',
    lg: '0 8px 16px 0 rgba(44, 62, 63, 0.12)',
    xl: '0 12px 24px 0 rgba(44, 62, 63, 0.15)',
    inner: 'inset 0 2px 4px 0 rgba(0, 0, 0, 0.05)',
  },

  // Focus ring (for accessibility)
  focusRing: {
    outline: '2px solid #5B7C6F',
    outlineOffset: '2px',
  },

  // Transitions
  transitions: {
    fast: '150ms cubic-bezier(0.4, 0, 0.2, 1)',
    base: '200ms cubic-bezier(0.4, 0, 0.2, 1)',
    slow: '300ms cubic-bezier(0.4, 0, 0.2, 1)',
  },

  // Container padding (responsive)
  container: {
    xs: '1rem',         // Mobile
    sm: '1.5rem',       // Small screens
    md: '2rem',         // Medium screens
    lg: '3rem',         // Large screens
    xl: '4rem',         // Extra large screens
  },
} as const;

// Component-specific spacing
export const componentSpacing = {
  // Button padding
  button: {
    sm: '0.5rem 1rem',           // 8px 16px
    base: '0.75rem 1.5rem',      // 12px 24px
    lg: '1rem 2rem',             // 16px 32px
  },

  // Form input padding
  input: {
    sm: '0.5rem 0.75rem',        // 8px 12px
    base: '0.75rem 1rem',        // 12px 16px
    lg: '1rem 1.25rem',          // 16px 20px
  },

  // Card padding
  card: {
    sm: '1rem',                  // 16px
    base: '1.5rem',              // 24px
    lg: '2rem',                  // 32px
  },

  // Spacing between sections
  section: '3rem',               // 48px

  // Gap between grid items
  gap: {
    xs: '0.75rem',               // 12px
    sm: '1rem',                  // 16px
    base: '1.5rem',              // 24px
    lg: '2rem',                  // 32px
    xl: '3rem',                  // 48px
  },
} as const;

export type SpacingTokens = typeof mindfulLearningSpacing;
export type ComponentSpacingTokens = typeof componentSpacing;
