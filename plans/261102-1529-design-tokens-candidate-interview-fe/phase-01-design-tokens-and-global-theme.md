---
phase: 1
title: "Design tokens + global theme"
status: done
priority: P1
dependencies: []
---

# Phase 1: Design tokens + global theme

## Overview
Replace the neutral shadcn starter theme with the token set extracted from `docs/design/*/*.dc.html`. Swap Geist for Inter. Align the shadcn primitives (button, badge, textarea, input, alert) with the design's controls. No API dependency, so this phase can start now.

## Requirements
- Functional: every color, radius, shadow, type size and container width the 4 artboards use has a named token. Tailwind utilities exist for each (`bg-success-subtle`, `rounded-3xl`, `shadow-card`, `text-meta`, `max-w-interview`, …).
- Non-functional: light theme only; tokens are hex values (exact design match); nothing outside `globals.css` hard-codes hex values; the existing `/` health page still renders.

## Design inventory (source of truth for the token values)
Extracted by frequency across `Interview.dc.html`, `Main.dc.html` (HR sign-in), `HRDashboard.dc.html`, `CandidateReview.dc.html`:
- Palette = Tailwind slate (text/borders) + blue-600 brand + green/amber/red status families.
- Type = Inter 400/500/600/700. Sizes 12 · 13 · 14 · 15 · 16 · 17 · 18 · 24 · 26 · 28 · 30 · 36 · 44 px.
- Radius = 4 · 7/8 · 9 · 10 · 12 · 14 · 16 · 18 · 999 px.
- Shadows = soft blue card glow, 1px control shadows, 3px focus halo.
- Containers = 760 (candidate), 1280 (HR), 420/480 (sign-in form).
- Control heights = 48 primary CTA · 46 input · 44 secondary · 40 tab · 38 HR button.
- HR status chips already exist as classes in the mockups (`.c-scored/.c-queued/.c-failed/.c-person/.c-hr`). They map to the status tokens below.

## Architecture: token definitions

### `:root` (raw values)
```css
:root {
  /* Surfaces */
  --background: #f8faff;          /* page background (candidate + HR) */
  --foreground: #0f172a;          /* primary text */
  --card: #ffffff;
  --card-foreground: #0f172a;
  --popover: #ffffff;
  --popover-foreground: #0f172a;
  --surface-subtle: #f8fafc;      /* HR side panel, table header */
  --dropzone: #f5f9ff;            /* audio drop area */

  /* Text scale */
  --foreground-soft: #1e293b;     /* form labels (sign-in) */
  --foreground-body: #334155;     /* long-form answer body */
  --muted-foreground: #475569;    /* meta, helper, secondary text */

  /* Brand (blue) */
  --primary: #2563eb;             /* CTA, filled progress, logo tile, focus outline */
  --primary-foreground: #ffffff;
  --primary-strong: #1d4ed8;      /* links, eyebrow labels, secondary button text, CTA hover */
  --primary-deep: #1e3a8a;        /* link hover */
  --primary-ink: #1e40af;         /* text on primary-subtle ("HR override" chip) */
  --primary-muted: #93c5fd;       /* current progress segment, dropzone dashed border */
  --primary-border: #bfdbfe;      /* secondary button border */
  --primary-subtle: #dbeafe;      /* icon bubble, focus halo, info chip bg */
  --primary-soft: #eff6ff;        /* soft panels, avatar, hover on secondary */

  /* shadcn semantic slots */
  --secondary: #ffffff;           /* secondary button = white + blue text + blue border */
  --secondary-foreground: #1d4ed8;
  --muted: #f1f5f9;               /* segmented-control track */
  --accent: #eff6ff;
  --accent-foreground: #1d4ed8;
  --destructive: #b91c1c;
  --border: #e2e8f0;              /* card + header borders, empty progress segment */
  --border-subtle: #eef2f7;       /* table row dividers */
  --input: #cbd5e1;               /* input/textarea border */
  --ring: #2563eb;

  /* Status: success (scored, receipt, "answers saved") */
  --success: #16a34a;
  --success-foreground: #ffffff;
  --success-soft: #f0fdf4;
  --success-subtle: #dcfce7;
  --success-border: #bbf7d0;
  --success-ink: #166534;
  --success-ink-strong: #14532d;

  /* Status: warning (needs a person, mock labels, injection highlight) */
  --warning-soft: #fffbeb;
  --warning-subtle: #fef3c7;
  --warning-border: #fde68a;
  --warning-border-strong: #fcd34d;
  --warning-ink: #92400e;
  --warning-ink-strong: #78350f;

  /* Status: danger (failed, errors) */
  --danger: #b91c1c;
  --danger-soft: #fef2f2;
  --danger-subtle: #fee2e2;
  --danger-border: #fecaca;
  --danger-ink: #991b1b;
  --danger-ink-strong: #7f1d1d;

  /* Status: neutral (queued) */
  --neutral-subtle: #e2e8f0;
  --neutral-ink: #334155;

  --radius: 0.75rem;              /* 12px base */
}
```

### `@theme inline` (Tailwind mapping)
Keep the existing shadcn color mappings. Add `--color-*` for every new var above (`--color-surface-subtle`, `--color-dropzone`, `--color-foreground-soft`, `--color-foreground-body`, `--color-primary-{strong,deep,ink,muted,border,subtle,soft}`, `--color-border-subtle`, `--color-success*`, `--color-warning*`, `--color-danger*`, `--color-neutral-*`). Then:

```css
@theme inline {
  --font-sans: var(--font-inter), ui-sans-serif, system-ui, sans-serif;

  /* Radius: explicit px, not the shadcn calc() ladder (the design uses fixed steps) */
  --radius-xs: 4px;    /* inline <mark> */
  --radius-sm: 8px;    /* logo tile, HR segmented thumb (7px → 8) */
  --radius-tab: 9px;   /* candidate answer-type tab thumb, HR buttons */
  --radius-md: 10px;   /* inputs, selects, sign-in CTA, soft panels */
  --radius-lg: 12px;   /* candidate CTA, textarea, tab track */
  --radius-xl: 14px;   /* receipt banner, dropzone */
  --radius-2xl: 16px;  /* HR cards */
  --radius-3xl: 18px;  /* candidate question card */

  /* Shadows */
  --shadow-card: 0 8px 24px rgb(37 99 235 / 0.06);
  --shadow-card-raised: 0 1px 2px rgb(15 23 42 / 0.04), 0 8px 24px rgb(37 99 235 / 0.06);
  --shadow-control: 0 1px 2px rgb(15 23 42 / 0.08);
  --shadow-tab: 0 1px 2px rgb(15 23 42 / 0.1);
  --shadow-focus: 0 0 0 3px var(--primary-subtle);

  /* Type scale (size / line-height / tracking) */
  --text-caption: 0.75rem;     --text-caption--line-height: 1.4;      /* 12: chips, uppercase labels */
  --text-meta: 0.8125rem;      --text-meta--line-height: 1.5;         /* 13: helper, progress label */
  --text-body-sm: 0.875rem;    --text-body-sm--line-height: 1.6;      /* 14: labels, secondary buttons */
  --text-body: 0.9375rem;      --text-body--line-height: 1.6;         /* 15: textarea, CTA, header title */
  --text-body-lg: 1rem;        --text-body-lg--line-height: 1.45;     /* 16: receipt title, HR question */
  --text-lead: 1.0625rem;      --text-lead--line-height: 1.6;         /* 17: sign-in hero lead */
  --text-title: 1.125rem;      --text-title--line-height: 1.4;        /* 18: brand name, avatar */
  --text-heading: 1.5rem;      --text-heading--line-height: 1.35;  --text-heading--letter-spacing: -0.015em; /* 24: candidate question */
  --text-heading-lg: 1.625rem; --text-heading-lg--line-height: 1.25; --text-heading-lg--letter-spacing: -0.02em; /* 26: HR candidate name */
  --text-display-sm: 1.75rem;  --text-display-sm--line-height: 1.2;  --text-display-sm--letter-spacing: -0.02em; /* 28: stat numbers, sign-in h2 */
  --text-display-md: 1.875rem; --text-display-md--line-height: 1.2;  --text-display-md--letter-spacing: -0.02em; /* 30: HR role title */
  --text-score: 2.25rem;       --text-score--line-height: 1;         --text-score--letter-spacing: -0.02em; /* 36: big score */
  --text-display: 2.75rem;     --text-display--line-height: 1.1;     --text-display--letter-spacing: -0.025em; /* 44: sign-in hero */

  /* Containers → max-w-* utilities */
  --container-interview: 47.5rem;  /* 760px candidate column */
  --container-app: 80rem;          /* 1280px HR shell */
  --container-auth: 26.25rem;      /* 420px sign-in form */
}
```
Control heights use the spacing scale: `h-12` (48), `h-11.5` (46), `h-11` (44), `h-10` (40), `h-9.5` (38).

### Base layer
```css
@layer base {
  * { @apply border-border outline-ring/50; }
  html { @apply font-sans antialiased; }
  body { @apply bg-background text-foreground; }
}
```
Delete the `.dark { … }` block, the `--chart-*` and `--sidebar-*` vars and their `@theme` mappings (unused; the design has none). Keep `@custom-variant dark`, which is harmless and stops shadcn `dark:` classes from erroring.

### shadcn primitive alignment (edit generated files in `src/components/ui/`)
| Component | Change |
|---|---|
| `button.tsx` | `default`: `hover:bg-primary-strong`. `secondary`: `border-primary-border bg-secondary text-secondary-foreground hover:bg-primary-soft`. `link`: `text-primary-strong hover:text-primary-deep`. Add sizes `xl` = `h-12 rounded-lg px-6 text-body font-semibold` (candidate CTA) and `cta` = `h-11 rounded-lg px-4 text-body-sm font-semibold` (secondary 44px). Keep existing sizes |
| `badge.tsx` | Add pill variants `success` / `warning` / `danger` / `info` / `neutral` = `rounded-full px-2.5 py-1 text-caption font-semibold` with `{status}-subtle` bg + `{status}-ink` text (info = `primary-subtle` + `primary-ink`). Matches the header "2 answers saved" pill and the HR chips |
| `textarea.tsx` | `rounded-lg border-input px-4 py-3.5 text-body leading-[1.6] text-foreground`; focus: `focus-visible:border-primary focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-primary` (the design's focus rule) |
| `input.tsx` | `h-11.5 rounded-md border-input px-3.5 text-body`; same focus rule |
| `alert.tsx` | Add `success` variant = `rounded-xl border-success-border bg-success-soft text-success-ink` (receipt banner). Make `destructive` use the `danger-*` tokens |

### Font (`src/app/layout.tsx`)
```tsx
import { Inter } from "next/font/google";
const inter = Inter({ subsets: ["latin"], weight: ["400", "500", "600", "700"], variable: "--font-inter" });
// <html lang="en" className={`${inter.variable} h-full`}>
```
This fixes the current self-reference (`--font-sans: var(--font-sans)`).

## Related Code Files
- Modify: `apps/web/src/app/globals.css`: full rewrite per above
- Modify: `apps/web/src/app/layout.tsx`: Inter, drop Geist/Geist_Mono
- Modify: `apps/web/src/components/ui/{button,badge,textarea,input,alert}.tsx`: variants/sizes above
- Create: `docs/design-guidelines.md`: token tables (name → hex/value → where used), control sizes, component recipes (question card, receipt, dropzone, segmented tabs, status chips), and the "light only, tokens only, no raw hex" rule

## Implementation Steps
1. Rewrite `globals.css` (`:root`, `@theme inline`, base layer). Remove dark/chart/sidebar.
2. Swap fonts in `layout.tsx`.
3. Patch the 5 shadcn primitives.
4. `cd apps/web && pnpm lint && pnpm typecheck && pnpm build`. Fix any `dark:`/removed-var fallout.
5. Load `/` in a browser: Inter renders, Badge/Card still look right (blue primary, slate borders).
6. Write `docs/design-guidelines.md`.

## Success Criteria
- [x] Every hex value in the 4 artboards maps to a token (spot check: `grep -oE '#[0-9A-F]{6}'` over the artboards → each value appears in `globals.css`)
- [x] Utilities resolve: `bg-success-subtle`, `text-primary-strong`, `rounded-3xl` (=18px), `shadow-card`, `text-meta`, `max-w-interview`
- [x] Inter loads; no Geist references left
- [x] `pnpm lint`, `pnpm typecheck`, `pnpm build` green; `/` health page renders
- [x] `docs/design-guidelines.md` written

## Risk Assessment
- Overriding `--radius-*` with fixed px changes every installed shadcn component's corners. This is intended (the design dictates radii). Check dialog/select visually.
- Removing `.dark` leaves `dark:` classes inert. That is fine, because no dark toggle exists.
- `@theme inline` with `--text-*--letter-spacing` needs Tailwind v4 (installed). If a sub-property is ignored, fall back to explicit `tracking-[-0.015em]` on the heading.
- Rollback: `git checkout` the 7 files. No data or API impact.
