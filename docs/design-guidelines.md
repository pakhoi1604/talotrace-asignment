# Design Guidelines

Token set extracted from the `docs/design/` artboards (4 screens: candidate interview, HR sign-in, HR dashboard, candidate review). **Light theme only** — the design has no dark theme.

**Rules**
- Components use tokens only — no raw hex values outside `apps/web/src/app/globals.css`.
- Raw values live in `:root`; Tailwind utilities come from the `@theme inline` mapping.
- Font: Inter 400/500/600/700 via `next/font/google` (`--font-inter`).

## Colors

### Surfaces & text
| Token | Hex | Used for |
|---|---|---|
| `background` | `#f8faff` | Page background |
| `card` / `popover` | `#ffffff` | Cards, question panel |
| `surface-subtle` | `#f8fafc` | HR side panel, table header |
| `dropzone` | `#f5f9ff` | Audio drop area |
| `foreground` | `#0f172a` | Primary text |
| `foreground-soft` | `#1e293b` | Form labels |
| `foreground-body` | `#334155` | Long-form answer body |
| `muted-foreground` | `#475569` | Meta, helper, secondary text |

### Brand (blue)
| Token | Hex | Used for |
|---|---|---|
| `primary` | `#2563eb` | CTA, filled progress, logo tile, focus outline |
| `primary-strong` | `#1d4ed8` | Links, secondary button text, CTA hover, active tab text |
| `primary-deep` | `#1e3a8a` | Link hover |
| `primary-ink` | `#1e40af` | Text on `primary-subtle` (info chips) |
| `primary-muted` | `#93c5fd` | Current progress segment, dropzone dashed border |
| `primary-border` | `#bfdbfe` | Secondary button border |
| `primary-subtle` | `#dbeafe` | Icon bubble, focus halo, info chip bg |
| `primary-soft` | `#eff6ff` | Soft panels, hover on secondary |

### Semantic / status
| Token | Hex | Used for |
|---|---|---|
| `secondary` / `secondary-foreground` | `#ffffff` / `#1d4ed8` | Secondary button (white + blue text/border) |
| `muted` | `#f1f5f9` | Segmented-control track |
| `accent` / `accent-foreground` | `#eff6ff` / `#1d4ed8` | Accent surfaces |
| `destructive` / `danger` | `#b91c1c` | Destructive actions, errors |
| `border` | `#e2e8f0` | Card + header borders, empty progress segment |
| `border-subtle` | `#eef2f7` | Table row dividers |
| `input` | `#cbd5e1` | Input/textarea border |
| `ring` | `#2563eb` | Focus ring |
| `success` | `#16a34a` | Scored, receipt icon, "answers saved" |
| `success-soft/-subtle/-border/-ink/-ink-strong` | `#f0fdf4` `#dcfce7` `#bbf7d0` `#166534` `#14532d` | Success surfaces → text |
| `warning-soft/-subtle/-border/-border-strong/-ink/-ink-strong` | `#fffbeb` `#fef3c7` `#fde68a` `#fcd34d` `#92400e` `#78350f` | Needs-a-person, mock labels |
| `danger-soft/-subtle/-border/-ink/-ink-strong` | `#fef2f2` `#fee2e2` `#fecaca` `#991b1b` `#7f1d1d` | Failed, errors |
| `neutral-subtle` / `neutral-ink` | `#e2e8f0` / `#334155` | Queued status |

Badge pill variants (`success` `warning` `danger` `info` `neutral`) = `{status}-subtle` bg + `{status}-ink` text; `info` = `primary-subtle` + `primary-ink`.

## Radius (fixed px — the design uses fixed steps, not a scale)
| Utility | Value | Used for |
|---|---|---|
| `rounded-xs` | 4px | Inline `<mark>` |
| `rounded-sm` | 8px | Logo tile, HR segmented thumb |
| `rounded-tab` | 9px | Answer-type tab thumb, HR buttons |
| `rounded-md` | 10px | Inputs, selects, sign-in CTA |
| `rounded-lg` | 12px | Candidate CTA, textarea, tab track |
| `rounded-xl` | 14px | Receipt banner, dropzone |
| `rounded-2xl` | 16px | HR cards |
| `rounded-3xl` | 18px | Candidate question card |

## Shadows
| Utility | Value | Used for |
|---|---|---|
| `shadow-card` | `0 8px 24px rgb(37 99 235 / .06)` | Question card, soft blue glow |
| `shadow-card-raised` | `0 1px 2px rgb(15 23 42/.04), 0 8px 24px rgb(37 99 235/.06)` | Raised cards |
| `shadow-control` | `0 1px 2px rgb(15 23 42 / .08)` | Controls |
| `shadow-tab` | `0 1px 2px rgb(15 23 42 / .1)` | Active tab thumb |
| `shadow-focus` | `0 0 0 3px var(--primary-subtle)` | Focus halo |

## Type scale (`text-*` sets size + line-height + tracking)
| Utility | Size | Used for |
|---|---|---|
| `text-caption` | 12px | Chips, uppercase labels |
| `text-meta` | 13px | Helper, progress label, footer |
| `text-body-sm` | 14px | Labels, secondary buttons |
| `text-body` | 15px | Textarea, CTA, header title |
| `text-body-lg` | 16px | Receipt title, HR question |
| `text-lead` | 17px | Sign-in hero lead |
| `text-title` | 18px | Brand name, avatar |
| `text-heading` | 24px (−0.015em) | Candidate question |
| `text-heading-lg` | 26px (−0.02em) | HR candidate name |
| `text-display-sm` | 28px (−0.02em) | Stat numbers, sign-in h2 |
| `text-display-md` | 30px (−0.02em) | HR role title |
| `text-score` | 36px (−0.02em) | Big score |
| `text-display` | 44px (−0.025em) | Sign-in hero |

## Containers & control heights
- `max-w-interview` 760px candidate column · `max-w-app` 1280px HR shell · `max-w-auth` 420px sign-in form
- Heights via spacing scale: `h-12` (48) primary CTA · `h-11.5` (46) input · `h-11` (44) secondary · `h-10` (40) tab · `h-9.5` (38) HR button

## Component recipes
- **Question card**: `rounded-3xl border bg-card p-6 sm:p-8 shadow-card` + heading `text-heading font-bold`
- **Page shell**: `min-h-full bg-background`; header `bg-card border-b`; inner `mx-auto max-w-interview px-6 py-4`; main `mx-auto max-w-interview px-6 pt-8 pb-16`
- **Receipt**: `Alert variant="success" role="status"` + check bubble `size-9 rounded-full bg-success` + title `text-body-lg font-bold text-success-ink-strong`
- **Dropzone**: dashed `border-2 border-primary-muted bg-dropzone rounded-xl`; dragover `border-primary bg-primary-soft`; mic bubble `size-12 rounded-full bg-primary-subtle`
- **Segmented tabs**: list `gap-1 rounded-lg bg-muted p-1`; trigger `h-10 px-4 rounded-tab text-body-sm font-medium text-muted-foreground`; active `bg-card text-primary-strong font-semibold shadow-tab`
- **Status chips**: `Badge` status variants above
- **Buttons**: `Button size="xl"` = 48px primary CTA · `size="cta"` = 44px secondary · `variant="secondary"` = white + `primary-border` + `primary-strong` text
- **Focus**: inputs/textarea use `border-primary` + `outline-2 outline-offset-1 outline-primary` (the design's focus rule); everything else keeps the ring
