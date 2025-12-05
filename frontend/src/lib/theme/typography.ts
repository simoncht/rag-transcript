/**
 * Typography System
 * Clean, accessible fonts for learning and focus
 */

export const mindfulLearningTypography = {
  // Font families
  fontFamilies: {
    heading: '"Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
    body: '"Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
    mono: '"SF Mono", "Monaco", "Courier Prime", monospace',
  },

  // Font sizes
  fontSize: {
    xs: '0.75rem',      // 12px
    sm: '0.875rem',     // 14px
    base: '1rem',       // 16px
    lg: '1.125rem',     // 18px
    xl: '1.25rem',      // 20px
    '2xl': '1.5rem',    // 24px
    '3xl': '1.875rem',  // 30px
    '4xl': '2.25rem',   // 36px
  },

  // Font weights
  fontWeight: {
    light: 300,
    normal: 400,
    medium: 500,
    semibold: 600,
    bold: 700,
  },

  // Line heights
  lineHeight: {
    tight: 1.2,
    snug: 1.375,
    normal: 1.5,
    relaxed: 1.625,
    loose: 2,
  },

  // Letter spacing
  letterSpacing: {
    tight: '-0.02em',
    normal: '0em',
    wide: '0.02em',
  },

  // Heading styles
  heading: {
    h1: {
      fontSize: '2.25rem',    // 36px
      fontWeight: 700,
      lineHeight: 1.2,
      letterSpacing: '-0.02em',
    },
    h2: {
      fontSize: '1.875rem',   // 30px
      fontWeight: 700,
      lineHeight: 1.2,
      letterSpacing: '-0.01em',
    },
    h3: {
      fontSize: '1.5rem',     // 24px
      fontWeight: 600,
      lineHeight: 1.375,
    },
    h4: {
      fontSize: '1.25rem',    // 20px
      fontWeight: 600,
      lineHeight: 1.375,
    },
    h5: {
      fontSize: '1.125rem',   // 18px
      fontWeight: 600,
      lineHeight: 1.5,
    },
    h6: {
      fontSize: '1rem',       // 16px
      fontWeight: 600,
      lineHeight: 1.5,
    },
  },

  // Body text styles
  body: {
    large: {
      fontSize: '1.125rem',   // 18px
      fontWeight: 400,
      lineHeight: 1.625,
    },
    base: {
      fontSize: '1rem',       // 16px
      fontWeight: 400,
      lineHeight: 1.625,
    },
    small: {
      fontSize: '0.875rem',   // 14px
      fontWeight: 400,
      lineHeight: 1.5,
    },
  },

  // Special text styles
  caption: {
    fontSize: '0.75rem',     // 12px
    fontWeight: 400,
    lineHeight: 1.5,
  },
  overline: {
    fontSize: '0.75rem',     // 12px
    fontWeight: 600,
    lineHeight: 1.5,
    letterSpacing: '0.02em',
    textTransform: 'uppercase' as const,
  },
} as const;

export type TypographyTokens = typeof mindfulLearningTypography;
