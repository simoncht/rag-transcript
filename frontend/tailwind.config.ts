import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      // Colors
      colors: {
        // Mindful Learning Theme
        primary: {
          50: "var(--color-primary-50)",
          100: "var(--color-primary-100)",
          main: "var(--color-primary)",
          light: "var(--color-primary-light)",
          lighter: "var(--color-primary-lighter)",
          dark: "var(--color-primary-dark)",
        },
        secondary: {
          main: "var(--color-secondary)",
          light: "var(--color-secondary-light)",
          dark: "var(--color-secondary-dark)",
        },
        accent: {
          main: "var(--color-accent)",
          light: "var(--color-accent-light)",
          dark: "var(--color-accent-dark)",
        },
        bg: {
          primary: "var(--color-bg-primary)",
          secondary: "var(--color-bg-secondary)",
          tertiary: "var(--color-bg-tertiary)",
        },
        text: {
          primary: "var(--color-text-primary)",
          secondary: "var(--color-text-secondary)",
          muted: "var(--color-text-muted)",
          light: "var(--color-text-light)",
        },
        border: {
          default: "var(--color-border)",
          hover: "var(--color-border-hover)",
        },
      },

      // Typography
      fontFamily: {
        heading: "var(--font-heading)",
        body: "var(--font-body)",
        mono: "var(--font-mono)",
      },
      fontSize: {
        xs: "0.75rem",
        sm: "0.875rem",
        base: "1rem",
        lg: "1.125rem",
        xl: "1.25rem",
        "2xl": "1.5rem",
        "3xl": "1.875rem",
        "4xl": "2.25rem",
      },

      // Spacing
      spacing: {
        0: "0",
        1: "0.25rem",
        2: "0.5rem",
        3: "0.75rem",
        4: "1rem",
        5: "1.25rem",
        6: "1.5rem",
        7: "1.75rem",
        8: "2rem",
        9: "2.25rem",
        10: "2.5rem",
        12: "3rem",
        16: "4rem",
        20: "5rem",
      },

      // Border Radius
      borderRadius: {
        none: "0",
        sm: "0.375rem",
        DEFAULT: "0.5rem",
        md: "0.75rem",
        lg: "1rem",
        xl: "1.5rem",
        full: "9999px",
      },

      // Shadows
      boxShadow: {
        none: "none",
        sm: "0 1px 2px 0 rgba(44, 62, 63, 0.05)",
        DEFAULT: "0 2px 8px 0 rgba(44, 62, 63, 0.08)",
        md: "0 4px 12px 0 rgba(44, 62, 63, 0.1)",
        lg: "0 8px 16px 0 rgba(44, 62, 63, 0.12)",
        xl: "0 12px 24px 0 rgba(44, 62, 63, 0.15)",
        inner: "inset 0 2px 4px 0 rgba(0, 0, 0, 0.05)",
      },

      // Transitions
      transitionDuration: {
        fast: "150ms",
        DEFAULT: "200ms",
        slow: "300ms",
      },
      transitionTimingFunction: {
        smooth: "cubic-bezier(0.4, 0, 0.2, 1)",
      },
    },
  },
  plugins: [],
};

export default config;
