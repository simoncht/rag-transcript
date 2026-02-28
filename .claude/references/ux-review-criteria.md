# UX Review Criteria - RAG Transcript

Project-specific design system reference for UX audits. Extracted from actual source files to avoid re-reading globals.css on every run.

## 1. Design Tokens (CSS Custom Properties)

Source: `frontend/src/app/globals.css`

### Custom Project Palette (`:root`)

| Token | Value | Usage |
|-------|-------|-------|
| `--color-primary` | `#5B7C6F` | Sage green - primary brand |
| `--color-primary-light` | `#7A9588` | Lighter sage |
| `--color-primary-lighter` | `#A8BFB7` | Subtle sage |
| `--color-primary-dark` | `#3D5348` | Dark sage |
| `--color-primary-50` | `#F5F8F7` | Very light sage bg |
| `--color-primary-100` | `#E8EEE8` | Light sage bg |
| `--color-secondary` | `#C89E6F` | Warm tan |
| `--color-secondary-light` | `#D4B896` | Light tan |
| `--color-secondary-dark` | `#A87D4C` | Dark tan |
| `--color-accent` | `#D4A574` | Soft terracotta |
| `--color-accent-light` | `#DEB899` | Light terracotta |
| `--color-accent-dark` | `#B88C5F` | Dark terracotta |
| `--color-bg-primary` | `#FDFBF7` | Main background (warm white) |
| `--color-bg-secondary` | `#F9F7F3` | Secondary background |
| `--color-bg-tertiary` | `#F5F2ED` | Tertiary background |
| `--color-text-primary` | `#2C3E3F` | Main text (dark teal) |
| `--color-text-secondary` | `#5A6B69` | Secondary text |
| `--color-text-muted` | `#8A9A98` | Muted text |
| `--color-text-light` | `#FDFBF7` | Light text (on dark bg) |
| `--color-border` | `#E8DCC8` | Default border |
| `--color-border-hover` | `#EFE9DD` | Hover border |
| `--color-success` | `#6B8E7F` | Success state |
| `--color-warning` | `#C89E6F` | Warning state |
| `--color-error` | `#B85C5C` | Error state |
| `--color-info` | `#5B7C6F` | Info state |

### Shadcn/Radix Theme Tokens (HSL format)

**Light mode (`:root`)**
| Token | HSL Value |
|-------|-----------|
| `--background` | `0 0% 100%` |
| `--foreground` | `0 0% 3.9%` |
| `--primary` | `0 0% 9%` |
| `--primary-foreground` | `0 0% 98%` |
| `--secondary` | `0 0% 96.1%` |
| `--muted` | `0 0% 96.1%` |
| `--muted-foreground` | `0 0% 45.1%` |
| `--accent` | `0 0% 96.1%` |
| `--destructive` | `0 84.2% 60.2%` |
| `--border` | `0 0% 89.8%` |

**Dark mode (`.dark`)**
| Token | HSL Value |
|-------|-----------|
| `--background` | `0 0% 3.9%` |
| `--foreground` | `0 0% 98%` |
| `--primary` | `0 0% 98%` |
| `--secondary` | `0 0% 14.9%` |
| `--muted` | `0 0% 14.9%` |
| `--muted-foreground` | `0 0% 63.9%` |
| `--border` | `0 0% 14.9%` |

**Important:** The project has **two color systems** running in parallel:
1. Custom `--color-*` variables (project palette) - used in `body`, headings, forms, links
2. Shadcn `--background`, `--foreground`, etc. (HSL) - used by Shadcn components via `bg-background`, `text-foreground`, etc.

Components should use Shadcn semantic classes (`bg-background`, `text-foreground`, `text-muted-foreground`, `bg-muted`, `border`) for dark mode compatibility. Custom `--color-*` variables do NOT have dark mode equivalents.

## 2. Component Inventory

### Shadcn UI Components Available (24)

| Component | File | Common Use |
|-----------|------|-----------|
| Avatar | `ui/avatar.tsx` | User avatars |
| Badge | `ui/badge.tsx` | Tags, status indicators |
| Button | `ui/button.tsx` | Actions (variants: default, destructive, outline, secondary, ghost, link) |
| Card | `ui/card.tsx` | Content containers |
| Checkbox | `ui/checkbox.tsx` | Multi-select |
| Collapsible | `ui/collapsible.tsx` | Expandable sections |
| Dialog | `ui/dialog.tsx` | Confirmation dialogs, modals |
| DropdownMenu | `ui/dropdown-menu.tsx` | Action menus, context menus |
| Input | `ui/input.tsx` | Text input |
| Label | `ui/label.tsx` | Form labels |
| Popover | `ui/popover.tsx` | Floating content |
| Progress | `ui/progress.tsx` | Progress bars, quota bars |
| ScrollArea | `ui/scroll-area.tsx` | Scrollable containers |
| Select | `ui/select.tsx` | Single option select |
| Separator | `ui/separator.tsx` | Visual dividers |
| Sheet | `ui/sheet.tsx` | Side panels, mobile nav |
| Skeleton | `ui/skeleton.tsx` | Loading placeholders |
| Switch | `ui/switch.tsx` | Toggles |
| Table | `ui/table.tsx` | Data tables |
| Tabs | `ui/tabs.tsx` | Tab navigation |
| Textarea | `ui/textarea.tsx` | Multi-line input |
| Toast/Toaster | `ui/toast.tsx` | Notifications |
| Tooltip | `ui/tooltip.tsx` | Hover hints |

### Correct Component Mapping

| UI Pattern | Use This Component | NOT This |
|------------|-------------------|----------|
| Confirmation dialog | `Dialog` | Custom modal div |
| Side panel / mobile nav | `Sheet` | Fixed position div |
| Dropdown actions | `DropdownMenu` | Custom popup |
| Loading placeholder | `Skeleton` | Spinner div |
| Status indicator | `Badge` | Styled span |
| Data list | `Table` | Custom grid divs |
| Form select | `Select` | Native `<select>` |
| Expandable section | `Collapsible` | Show/hide with state |

## 3. Layout Conventions

Source: `MainLayout.tsx`

### Page Structure
```
<div className="flex min-h-screen w-full bg-muted/40">
  <aside className="hidden w-64 flex-col border-r bg-background/90 lg:flex">
    <!-- Sidebar: 64rem wide, hidden on mobile -->
  </aside>
  <div className="flex flex-1 flex-col">
    <header className="flex h-16 items-center gap-3 border-b bg-background px-4 lg:px-6">
      <!-- Top bar -->
    </header>
    <main className="flex-1 overflow-y-auto bg-background px-4 py-6 lg:px-8 lg:py-10">
      <div className="mx-auto w-full max-w-6xl">{children}</div>
    </main>
  </div>
</div>
```

### Spacing Pattern
- **Mobile**: `px-4 py-6`
- **Desktop (lg+)**: `px-8 py-10`
- **Max content width**: `max-w-6xl` (72rem / 1152px)
- **Sidebar width**: `w-64` (16rem / 256px)
- **Header height**: `h-16` (4rem / 64px)
- **Nav item padding**: `px-3 py-2`
- **Card internal padding**: Typically `p-4` or `p-6`

### Breakpoints
- `lg` (1024px): Sidebar shows, padding increases
- `sm` (640px): Some header elements show
- Mobile-first: Everything else

## 4. Typography Scale

| Class | Size | Usage |
|-------|------|-------|
| `text-lg font-semibold` | 1.125rem | Section headers, sidebar brand |
| `text-base font-semibold` | 1rem | Brand text, primary content |
| `text-sm font-medium` | 0.875rem | Nav items, card titles, body text |
| `text-sm` | 0.875rem | General body text |
| `text-xs` | 0.75rem | Metadata, labels (e.g., "QUOTA") |
| `text-[11px]` | 0.6875rem | Compact metadata (use sparingly) |
| `text-[10px]` | 0.625rem | Micro text - accessibility concern |

**Font family**: Inter (via `--font-heading`, `--font-body`)

## 5. WCAG AA Requirements

### Contrast Ratios (Minimum)
| Content Type | Ratio | Example |
|-------------|-------|---------|
| Normal text (<18px / <14px bold) | 4.5:1 | Body copy, labels |
| Large text (>=18px / >=14px bold) | 3:1 | Headings |
| UI components & graphical objects | 3:1 | Buttons, icons, borders |

### Focus Indicators
- All interactive elements must have visible focus indicator
- Default: `outline: 2px solid var(--color-primary)` with `outline-offset: 2px`
- Shadcn components handle this via `focus-visible:ring-2 ring-ring`
- Custom `<button>` elements must explicitly add focus styles

### Touch Targets
- Minimum 44x44px on mobile for all interactive elements
- Check sidebar nav items, action buttons, close icons

### Keyboard Navigation
- All interactive content reachable via Tab key
- Modal dialogs must trap focus
- Escape key should close modals/sheets

## 6. Known Anti-Patterns to Flag

### Hardcoded Colors (378 occurrences across 36 files)
Files with highest counts of `text-gray-*`, `bg-white`, `bg-gray-*`, `border-gray-*`:
- `frontend/src/components/videos/DeleteConfirmationModal.tsx` (36)
- `frontend/src/app/privacy/page.tsx` (22)
- `frontend/src/app/terms/page.tsx` (27)
- `frontend/src/components/collections/CollectionModal.tsx` (23)
- `frontend/src/components/videos/CancelConfirmationModal.tsx` (24)
- `frontend/src/components/videos/AddToCollectionModal.tsx` (28)
- Landing page components (FeaturesSection, HeroSection, PricingSection, etc.)

**Impact:** These break in dark mode. Should use `text-foreground`, `text-muted-foreground`, `bg-background`, `bg-muted`, `border` instead.

### Micro Text (`text-[10px]` and `text-[11px]`)
Heavy usage in:
- `frontend/src/app/conversations/[id]/page.tsx` (~20 instances)
- `frontend/src/components/shared/CitationBadge.tsx`
- `frontend/src/components/insights/TopicDetailPanel.tsx`
- `frontend/src/app/videos/page.tsx`

**Impact:** `text-[10px]` is 10px which may fail WCAG AA contrast at low-contrast color combinations. The minimum recommended body text size is 12px.

### Non-Standard Accent Classes
Files using `bg-accent-main`, `text-accent-dark`, `bg-accent-*` outside Shadcn system:
- `frontend/src/components/shared/CitationBadge.tsx`
- `frontend/src/components/shared/Button.tsx`
- `frontend/src/components/ui/button.tsx`
- `frontend/src/components/ui/select.tsx`
- `frontend/src/components/ui/dropdown-menu.tsx`

**Impact:** These classes reference the custom `--color-accent` tokens that have no dark mode equivalent.

### Dual Color System Confusion
The project has both:
1. Custom `--color-*` CSS variables (no dark mode)
2. Shadcn HSL variables (has dark mode via `.dark` class)

Components mixing these two systems will have inconsistent dark mode behavior. Prefer Shadcn semantic classes for all new code.

## 7. App Routes (25 pages)

| Route | Purpose | Layout |
|-------|---------|--------|
| `/` | Landing page | Custom (no MainLayout) |
| `/videos` | Video library | MainLayout |
| `/collections` | Collection management | MainLayout |
| `/conversations` | Conversation list | MainLayout |
| `/conversations/[id]` | Chat interface | MainLayout |
| `/pricing` | Pricing plans | Custom |
| `/account` | Account settings | MainLayout |
| `/subscriptions` | Subscription management | MainLayout |
| `/get-started` | Onboarding | Custom |
| `/admin` | Admin dashboard | MainLayout |
| `/admin/users` | User management | MainLayout |
| `/admin/users/[id]` | User detail | MainLayout |
| `/admin/videos` | Video management | MainLayout |
| `/admin/conversations` | Conversation review | MainLayout |
| `/admin/qa` | QA feed | MainLayout |
| `/admin/usage` | Usage analytics | MainLayout |
| `/admin/alerts` | System alerts | MainLayout |
| `/admin/collections` | Collection management | MainLayout |
| `/checkout/start` | Checkout initiation | Custom |
| `/checkout/success` | Checkout success | Custom |
| `/checkout/cancel` | Checkout cancel | Custom |
| `/login` | Login | Custom |
| `/sign-in/[...]` | Auth (Clerk) | Custom |
| `/privacy` | Privacy policy | Custom |
| `/terms` | Terms of service | Custom |

Pages with "Custom" layout bypass MainLayout and are more prone to design system inconsistency.
