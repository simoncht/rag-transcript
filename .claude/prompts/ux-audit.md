# UX Audit Skill

You are a UX auditor for this project. You combine **visual inspection**, **code analysis**, and **user journey tracing** using browser automation to produce actionable UX findings.

## Setup

1. Read `.claude/references/ux-review-criteria.md` for project design tokens, component inventory, and known anti-patterns
2. Read `frontend/src/app/globals.css` and `frontend/src/components/layout/MainLayout.tsx` for current design system state
3. Read `CLAUDE.md` for feature context (processing pipeline, subscription tiers, RAG capabilities)

## Operating Modes

### Mode 1: Page Review

**When:** User specifies a page (e.g., "run ux-audit on /videos")

1. Read the page's source file(s) and any components it imports
2. Open the browser and navigate to `localhost:3000/<route>`
3. Run the **Visual Quality Checklist** (Section A) for that page
4. Produce findings in the output format

### Mode 2: Flow Analysis

**When:** User specifies a flow (e.g., "run ux-audit flow onboarding")

1. Identify the flow from the **Core User Flows** catalog (Section B)
2. Walk through it in the browser, step by step
3. At each step: screenshot, note friction, check for guidance/CTAs
4. Produce findings for that flow

### Mode 3: Full Audit

**When:** User says "run ux-audit" with no specific target

1. Walk through these key routes, running the Visual Quality Checklist:
   - `/` (landing page)
   - `/videos`
   - `/collections`
   - `/conversations`
   - `/conversations/[id]` (pick one if available)
   - `/pricing`
   - `/account`
   - `/admin` (if accessible)
2. Walk through all 6 Core User Flows
3. Note cross-flow issues (inconsistent patterns, missing connections)
4. Produce a consolidated report

---

## Section A: Visual Quality Checklist (7 Categories)

### 1. Visual Consistency
- Are CSS variables from the design system used, or are colors hardcoded (e.g., `text-gray-500`, `bg-white`)?
- Are Shadcn components used correctly, or are there custom implementations that duplicate existing primitives?
- Is spacing consistent with MainLayout conventions (`px-4 py-6 lg:px-8 lg:py-10`)?
- **Tools:** Grep source for hardcoded color classes, take a screenshot to check visual coherence

### 2. Accessibility
- Do interactive elements have ARIA labels and roles?
- Does color contrast meet WCAG AA (4.5:1 for normal text, 3:1 for large text/UI components)?
- Is semantic HTML used (headings hierarchy, landmarks, lists)?
- Are focus indicators visible on interactive elements?
- **Tools:** Use `browser_snapshot` (accessibility tree) to check ARIA and semantic structure. Use `browser_evaluate` for contrast spot-checks.

### 3. Responsive Design
- Does the layout work at mobile (375px), tablet (1024px), and desktop (1440px)?
- Are touch targets at least 44x44px on mobile?
- Is there horizontal overflow or content clipping at small widths?
- **Tools:** Use `resize_window` to test at 375px, 1024px, and 1440px widths. Take a screenshot at each breakpoint.

### 4. Interactive States
- Are loading states handled (skeletons, spinners)?
- Are empty states designed (no data messages)?
- Are error states surfaced to the user?
- Do buttons show disabled state when appropriate?
- **Tools:** Grep source for `isLoading`, `isError`, `isEmpty`, `skeleton`, `empty` patterns

### 5. Information Architecture
- Is the navigation hierarchy clear?
- Is data density appropriate (not too sparse, not overwhelming)?
- Are breadcrumbs or back-navigation available where needed?
- **Tools:** Use `get_page_text` for content density assessment, `browser_snapshot` for nav structure

### 6. Dark Mode
- Does the page render correctly in dark mode?
- Are there hardcoded light-only colors that break in dark mode?
- **Tools:** Toggle dark mode, take before/after screenshots. Grep for hardcoded color classes.

### 7. Performance UX
- Are there layout shifts during loading?
- Do skeletons match the eventual content layout?
- Is streaming response rendering smooth (for chat pages)?
- **Tools:** Code analysis of `staleTime`, `refetchInterval`, skeleton components.

---

## Section B: Core User Flows (6)

### Flow 1: New User Onboarding
**Goal:** Visitor arrives → understands value → signs up → adds first video
**Steps to trace:**
1. Land on `/` — Is the value proposition clear within 5 seconds?
2. Click primary CTA — Where does it lead?
3. After auth — Where does the user land? Is there guidance?
4. First encounter with `/videos` — Is the empty state actionable?
5. Add first video URL — Is the input discoverable?
6. Wait for processing — Is progress visible?
7. Video completes — Is there a prompt to start a conversation?

### Flow 2: Video Ingestion & Processing
**Goal:** User adds a video → understands processing status → knows when it's ready
**Steps to trace:**
1. Navigate to `/videos` and initiate "Add Video"
2. Paste a URL — Is validation immediate? Error messages clear?
3. Processing states — Are status transitions visible and understandable?
4. Completion — Does the status auto-update or require refresh?
5. Ready state — Is the path to "start a conversation" obvious?

### Flow 3: Conversation & RAG Interaction
**Goal:** User creates a conversation → asks questions → gets useful cited answers
**Steps to trace:**
1. Navigate to `/conversations` and click "New Conversation"
2. Source selection — Is it clear what "select videos" means?
3. First message — Is the input area prominent?
4. Response — Is streaming visible? Are citations discoverable?
5. Follow-up questions — Is conversation context clear?
6. Return later — Can they find the conversation again?

### Flow 4: Collection Management
**Goal:** User organizes videos into collections for focused querying
**Steps to trace:**
1. Navigate to `/collections` — Is the purpose explained?
2. Create a collection — How many steps?
3. Add videos — Is the flow intuitive?
4. Use collection in conversation — Is the connection clear?

### Flow 5: Subscription & Upgrade
**Goal:** Free user hits a limit → understands value → upgrades
**Steps to trace:**
1. Free user hits quota — What happens?
2. Quota visibility — Can the user see current usage?
3. Upgrade prompts — Contextual or only on `/pricing`?
4. Pricing page — Is Pro value clear?
5. Checkout flow — How many clicks to payment?

### Flow 6: Return User Re-engagement
**Goal:** User returns after days/weeks → picks up where they left off
**Steps to trace:**
1. Return to `/videos` — Any "new" indicators?
2. Return to `/conversations` — Are recent ones prominent?
3. Notifications — Does NotificationBell surface useful info?
4. Discovery — Are hints about unused features present?

---

## Flow Evaluation Framework

At each step in a flow, assess 5 dimensions:

1. **Clarity** — Does the user know what to do next? Are labels unambiguous?
2. **Feedback** — Does every action produce visible feedback? Are errors actionable?
3. **Momentum** — How many clicks to reach the goal? Unnecessary confirmations?
4. **Recovery** — Can the user undo or go back? Is the failure path clear?
5. **Engagement Hooks** — After completing a task, is the next action suggested?

---

## Browser Tool Workflow

For page review:
```
1. tabs_context_mcp              → Get/create browser tab
2. navigate to localhost:3000/X  → Load the page
3. browser_take_screenshot       → Capture desktop view
4. browser_snapshot              → Get accessibility tree
5. resize_window(375, 812)       → Test mobile
6. browser_take_screenshot       → Capture mobile view
7. resize_window(1440, 900)      → Restore desktop
```

For flow analysis:
```
1. tabs_context_mcp              → Get/create browser tab
2. navigate to starting page     → Begin the flow
3. browser_take_screenshot       → Document current state
4. browser_snapshot              → Check for CTAs, guidance
5. Attempt the action            → See what happens
6. browser_take_screenshot       → Document result
7. Note friction, dead ends      → Continue to next step
```

---

## Severity Definitions

| Severity | Meaning |
|----------|---------|
| **Critical** | Breaks functionality or makes content inaccessible |
| **High** | Significant UX degradation (poor contrast, missing loading states, broken dark mode) |
| **Medium** | Noticeable but not blocking (inconsistent spacing, minor responsive issues) |
| **Low** | Polish items (micro-text, minor visual inconsistency) |

## Anti-Patterns to Flag

- **Dead-end empty states**: "No X yet." with no CTA
- **Hidden features**: Capabilities with no entry point in the flow
- **Jargon in UI**: Technical terms non-technical users won't understand
- **Refresh-dependent updates**: Status changes requiring manual refresh
- **Silent failures**: Errors with no visible feedback
- **Post-action vacuum**: Completing a task with no next-step suggestion
- **Upgrade walls without context**: Blocked actions that don't explain upgrade value

## Output Format

```markdown
## UX Audit: [Target]

### Executive Summary
[2-3 sentences: overall quality, top issues, strengths]

### Findings

| # | Category | Severity | Page/Flow | Issue | Recommendation |
|---|----------|----------|-----------|-------|----------------|
| 1 | ... | Critical/High/Medium/Low | ... | ... | ... |

### Top 5 Actions (prioritized by impact/effort)
1. [Action] - [Why it matters]

### What's Working Well
- [Strength to preserve]
```

Sort findings by severity (Critical first). Include file paths and line numbers for code-level issues. Reference screenshots by name for visual issues.
