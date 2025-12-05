/**
 * Complete Theme System
 * Combines colors, typography, spacing into a unified design system
 */

import { mindfulLearningColors, type ColorTokens } from './colors';
import { mindfulLearningTypography, type TypographyTokens } from './typography';
import { mindfulLearningSpacing, componentSpacing, type SpacingTokens, type ComponentSpacingTokens } from './spacing';

export type Theme = {
  colors: ColorTokens;
  typography: TypographyTokens;
  spacing: SpacingTokens;
  componentSpacing: ComponentSpacingTokens;
};

export const mindfulLearningTheme: Theme = {
  colors: mindfulLearningColors,
  typography: mindfulLearningTypography,
  spacing: mindfulLearningSpacing,
  componentSpacing,
};

// Re-export for convenience
export { mindfulLearningColors, mindfulLearningTypography, mindfulLearningSpacing, componentSpacing };
export type { ColorTokens, TypographyTokens, SpacingTokens, ComponentSpacingTokens };
