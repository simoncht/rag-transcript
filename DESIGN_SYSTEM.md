# Mindful Learning Design System

A comprehensive, themeable design system for sustainable learning engagement.

## Philosophy

Users spend hours learning and chatting with AI about video content. The interface must:
- ✅ Be beautiful enough to attract users
- ✅ Be warm and approachable (not cold/mechanical)
- ✅ Not fatigue the eyes or mind after long study sessions
- ✅ Feel professional and intentional
- ✅ Be **trivially easy to theme/reskin** in the future

## Design Direction

**"Mindful Learning"** - A warm, elegant aesthetic supporting serious, sustained focus.

### Color Palette

| Component | Color | Hex | Purpose |
|-----------|-------|-----|---------|
| **Primary** | Sage Green | #5B7C6F | Main brand color, buttons, links, active states |
| **Primary Light** | Light Sage | #7A9588 | Hover states, light backgrounds |
| **Primary Dark** | Dark Sage | #3D5348 | Emphasis, darker text on light backgrounds |
| **Secondary** | Warm Tan | #C89E6F | Secondary accents, warnings, secondary buttons |
| **Accent** | Soft Terracotta | #D4A574 | Citations, CTAs, highlights |
| **BG Primary** | Cream | #FDFBF7 | Main background (warm white) |
| **BG Secondary** | Off-white | #F9F7F3 | Surface areas (chat window, cards) |
| **Text Primary** | Warm Charcoal | #2C3E3F | Main text (not pure black) |
| **Text Secondary** | Medium Gray | #5A6B69 | Secondary text, help text |
| **Border** | Beige | #E8DCC8 | Dividers, subtle borders |

**Why these colors?**
- Warm, not cool (no blues that feel "tech")
- Natural, not vibrant (won't cause eye fatigue)
- Accessible (high contrast ratios)
- Professional (not childish or cartoonish)
- Timeless (won't feel dated in 2 years)

### Typography

| Use | Font | Weight | Size |
|-----|------|--------|------|
| **Headings** | Inter | 700 (bold) | 18-36px |
| **Body** | Inter | 400 (normal) | 14-16px |
| **Code/Mono** | SF Mono | 400 | 12-14px |

**Why Inter?**
- Modern, geometric, warm personality
- Excellent readability at all sizes
- Google Fonts (no licensing issues)
- Used by Stripe, Vercel, hundreds of successful products

### Spacing Scale

Based on 4px unit (every component aligns to 4px grid):

```
1 = 4px    6 = 24px   12 = 48px
2 = 8px    7 = 28px   16 = 64px
3 = 12px   8 = 32px   20 = 80px
4 = 16px   9 = 36px
5 = 20px   10 = 40px
```

### Shadows

- **sm**: Micro-interactions (1px y, 2px blur)
- **base**: Default cards and buttons
- **md**: Elevated components
- **lg**: Modal overlays
- **None**: Flat designs (some borders)

*All shadows are soft (0.05-0.15 opacity) to match warm aesthetic*

### Transitions

- **fast** (150ms): Micro-interactions, hovers
- **base** (200ms): Default transitions, inputs
- **slow** (300ms): Modals, major layout changes
- **easing**: `cubic-bezier(0.4, 0, 0.2, 1)` (smooth, natural)

## Component Architecture

### Token System

All design decisions live in `/frontend/src/lib/theme/`:

```
theme/
├── colors.ts       # Color definitions
├── typography.ts   # Font families, sizes, weights
├── spacing.ts      # Spacing, shadows, transitions
└── index.ts        # Unified export
```

### CSS Variables

Global CSS variables in `globals.css` for runtime switching:

```css
--color-primary: #5B7C6F
--color-primary-light: #7A9588
--color-primary-dark: #3D5348
/* ... more colors ... */
--font-heading: 'Inter', sans-serif
--font-body: 'Inter', sans-serif
--font-mono: 'SF Mono', monospace
```

### Tailwind Integration

Custom Tailwind config reads from theme tokens:

```typescript
// tailwind.config.ts
colors: {
  primary: {
    main: "var(--color-primary)",
    light: "var(--color-primary-light)",
    dark: "var(--color-primary-dark)",
  },
  // ...
}
```

## Components

### MessageBubble
Chat message with dynamic coloring, citations, timestamps.

**Props:**
- `text: string` - Message content
- `isUser: boolean` - Whether this is user or assistant
- `citations?: ChunkReference[]` - Citation references
- `timestamp?: Date` - Message timestamp
- `responseTime?: number` - Response time in ms

**Example:**
```tsx
<MessageBubble
  text="The speaker argues..."
  isUser={false}
  citations={[...]}
  responseTime={1250}
/>
```

### CitationBadge
Inline citation reference with expandable details.

**Props:**
- `citation: ChunkReference` - Citation data
- `index: number` - Citation number for display
- `onTimestampClick?: (ts: string) => void` - Click handler

**Features:**
- Shows relevance score
- Expandable modal with snippet preview
- Clickable timestamp
- Accessible focus states

### Button
Theme-aware button with multiple variants and sizes.

**Props:**
- `variant?: 'primary' | 'secondary' | 'accent' | 'outline' | 'ghost'`
- `size?: 'sm' | 'base' | 'lg'`
- `isLoading?: boolean`
- `disabled?: boolean`

**Examples:**
```tsx
<Button variant="primary" size="base">Save</Button>
<Button variant="outline" size="sm">Cancel</Button>
<Button variant="ghost">Learn More</Button>
```

### Card
Container component with soft shadows and elegant borders.

**Props:**
- `children: React.ReactNode`
- `isPressable?: boolean` - Makes it clickable
- `onClick?: () => void`
- `hoverable?: boolean` - Enable hover effects

### Badge
Status indicator with semantic color variants.

**Props:**
- `variant?: 'success' | 'warning' | 'error' | 'info' | 'default'`
- `children: React.ReactNode`

## Theming Strategy

### Current Theme
**Mindful Learning** - Warm, elegant aesthetic for learning

### To Create a New Theme

1. **Copy token files** to create new versions:
   ```
   src/lib/theme/mindful-learning/
   └── colors.ts
   ```

2. **Update globals.css** CSS variable values

3. **Switch in app**:
   ```tsx
   // Import your new theme tokens
   import { newThemeColors } from '@/lib/theme/new-theme/colors'
   ```

4. **No component changes needed** - All components use CSS variables!

### Example: Dark Theme
To create a dark theme, only change CSS variables:

```css
:root {
  --color-bg-primary: #1a1a1a;      /* Was: cream */
  --color-bg-secondary: #2d2d2d;    /* Was: off-white */
  --color-text-primary: #f5f5f5;    /* Was: charcoal */
  --color-border: #404040;          /* Was: beige */
  /* Keep colors the same, just invert backgrounds */
}
```

## Usage in Components

### Accessing Theme Values

All components automatically get theme tokens through CSS variables:

```tsx
// Example: Using theme colors in a component
export const MyComponent = () => {
  return (
    <div className="bg-bg-secondary text-text-primary border border-border-default">
      <h2 className="font-heading text-primary">Themed Heading</h2>
    </div>
  );
};
```

### Using Theme Hook (if needed)

For dynamic color logic:

```tsx
import { mindfulLearningTheme } from '@/lib/theme'

export const DynamicComponent = () => {
  const primaryColor = mindfulLearningTheme.colors.primary.main;
  // Use as needed
}
```

## Accessibility

✅ **Color Contrast**
- All text meets WCAG AA standards (4.5:1 for body, 3:1 for UI components)
- Focus rings visible on all interactive elements
- No color-only differentiation

✅ **Keyboard Navigation**
- All buttons and links have proper focus states
- Tab order is logical and predictable
- Skip links for main content

✅ **Motion**
- Transitions use accessible easing
- No seizure-inducing animations
- Respects `prefers-reduced-motion` preference

## Development

### Building Components

Always start with theme tokens, never hardcode colors:

❌ **Bad:**
```tsx
<div className="bg-blue-500 text-gray-900">Bad</div>
```

✅ **Good:**
```tsx
<div className="bg-primary text-text-primary">Good</div>
```

### Testing Theme Changes

1. Update CSS variable in `globals.css`
2. All components automatically reflect change
3. No component code changes needed

## Files Overview

```
frontend/
├── src/
│   ├── lib/theme/           ← All design tokens live here
│   │   ├── colors.ts
│   │   ├── typography.ts
│   │   ├── spacing.ts
│   │   └── index.ts
│   ├── components/shared/   ← Reusable theme-aware components
│   │   ├── MessageBubble.tsx
│   │   ├── CitationBadge.tsx
│   │   ├── Button.tsx
│   │   ├── Card.tsx
│   │   ├── Badge.tsx
│   │   └── index.ts
│   └── app/globals.css      ← CSS variables & global styles
├── tailwind.config.ts       ← Tailwind theme config
└── next.config.js
```

## Best Practices

1. **Use Tailwind classes** for styling (composable, responsive)
2. **Reference theme tokens** in custom CSS for complex layouts
3. **Avoid hardcoded colors** - always use CSS variables
4. **Test on real devices** - colors look different on phone vs desktop
5. **Check contrast** - use WebAIM or similar tools
6. **Respect preferences** - test with `prefers-reduced-motion` and dark mode settings

## Future Enhancements

- [ ] Dark mode variant (automatic CSS variable switching)
- [ ] Light mode variant for accessibility
- [ ] Animated transitions and micro-interactions
- [ ] Custom theme builder UI
- [ ] Per-user theme preferences
- [ ] A/B testing theme variants

## Resources

- [Inter Font](https://rsms.me/inter/)
- [Tailwind CSS](https://tailwindcss.com/)
- [Next.js Best Practices](https://nextjs.org/docs)
- [WCAG Accessibility](https://www.w3.org/WAI/WCAG21/quickref/)
- [Color Contrast Checker](https://webaim.org/resources/contrastchecker/)
