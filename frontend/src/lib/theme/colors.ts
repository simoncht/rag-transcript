/**
 * Mindful Learning Color Palette
 * A warm, accessible theme for sustainable learning engagement
 */

export const mindfulLearningColors = {
  // Primary Colors
  primary: {
    main: '#5B7C6F',      // Sage green - main brand color
    light: '#7A9588',     // Lighter sage for hover states
    lighter: '#A8BFB7',   // Light sage for disabled states
    dark: '#3D5348',      // Dark sage for emphasis
  },

  // Secondary Colors (Warm accents)
  secondary: {
    main: '#C89E6F',      // Warm tan - secondary accent
    light: '#D4B896',     // Light tan
    dark: '#A87D4C',      // Dark tan
  },

  // Accent Colors (Citations, CTAs)
  accent: {
    main: '#D4A574',      // Soft terracotta - calls to action
    light: '#DEB899',     // Light terracotta
    dark: '#B88C5F',      // Dark terracotta
  },

  // Background Colors
  background: {
    primary: '#FDFBF7',   // Cream - main background
    secondary: '#F9F7F3', // Off-white - surface areas (chat)
    tertiary: '#F5F2ED',  // Light beige - subtle backgrounds
  },

  // Text Colors
  text: {
    primary: '#2C3E3F',   // Warm charcoal - main text
    secondary: '#5A6B69', // Medium gray - secondary text
    muted: '#8A9A98',     // Muted gray - disabled, helper text
    light: '#FDFBF7',     // Light text for dark backgrounds
  },

  // Neutral/Dividers
  neutral: {
    border: '#E8DCC8',    // Beige - borders and dividers
    hover: '#EFE9DD',     // Hover state for neutral elements
    disabled: '#E5E0D5',  // Disabled state
  },

  // Status Colors
  status: {
    success: '#6B8E7F',   // Green (uses primary)
    warning: '#C89E6F',   // Orange (uses secondary)
    error: '#B85C5C',     // Warm red
    info: '#5B7C6F',      // Info (uses primary)
  },

  // Semantic Colors
  semantic: {
    citation: '#D4A574',  // Accent color for citations
    active: '#5B7C6F',    // Primary for active states
    hover: '#7A9588',     // Primary light for hover
    focus: '#5B7C6F',     // Primary for focus rings
  },
} as const;

export type ColorTokens = typeof mindfulLearningColors;
