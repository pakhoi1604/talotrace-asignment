---
phase: 3
title: "Candidates per role"
status: completed
priority: P1
dependencies: [2]
---

# Phase 3: Candidates per role

## Overview
`/hr/roles/[roleId]` faithful to `HRDashboard.dc.html`: role title + switcher, 6 stat cards, candidate table with client-side sort, Review links.

## Requirements
- Functional: switch role (navigates to `/hr/roles/{id}`); stats aggregated from the response; table per candidate; sort Name (default) · Highest score · Newest; Refresh button (no auto-refresh).
- Non-functional: table scrolls horizontally on narrow screens (`min-w-[880px]` inside `overflow-x-auto`); semantic `<table>` with `<th scope="col">`; the sort control is a `role="radiogroup"` (or `aria-pressed` buttons); tokens only.

## Architecture

### Data
<!-- Updated: Validation Session 1 - polling replaced by Refresh button -->
- `useHrResource(() => getRoleCandidates(roleId), [roleId])`; `<RefreshButton>` in the title row calls `reload()`.
- `useHrResource(listRoles, [])` for the switcher and "Open roles · N".
- 404 `role not found` → "This role doesn't exist" card + link to `/hr`.

### Derived values (`src/lib/hr-role-stats.ts`, pure)
```ts
roleStats(rc: RoleCandidates) → { candidates, answers, scored, queued /* queued+running */, failed, needsPerson }
candidateNote(c: CandidateRow) → string
  // failed > 0 → "{n} answer(s) failed to score"
  // needs_person > 0 → "{n} answer(s) need a person"
  // queued+running > 0 → "Scoring in progress"
  // answered_count === 0 → "No answers yet"
  // answered_count < total → "{a} of {t} answered"
  // else → "All answers scored"
sortCandidates(rows, mode: "name" | "highest" | "newest") → CandidateRow[]
  // name: API order (already by name), returned as-is
  // highest: avg_final ?? avg_suggested, desc; nulls last; tie → name
  // newest: last_activity_at desc; nulls last; tie → name
```
Notes are derived only from counts the API returns. Never invent reasons.

### Components (`src/components/hr/role/`)
| File | Responsibility | Design ref |
|---|---|---|
| `role-candidates-screen.tsx` | client root: data, sort state (`useState`, default `"name"`), loading skeleton, error alert + Retry | whole artboard |
| `role-header.tsx` | eyebrow `text-meta font-medium text-muted-foreground` "Open roles · {n}"; h1 `text-display-md font-bold` role title; `Select` (shadcn, exists) of roles with `sr-only` label "Role", `h-11 rounded-md`; on change `router.push(/hr/roles/{id})`; `RefreshButton` beside it. **No "Load data pack" button** | title row |
| `role-stat-cards.tsx` | `grid grid-cols-[repeat(auto-fit,minmax(170px,1fr))] gap-4`; card `rounded-xl border bg-card px-5 py-4.5`; Candidates, Answers (plain labels), then Scored/Queued/Failed/Needs a person with `JobStatusChip`; Failed card `border-danger-border`, Needs a person `border-warning-border`; number `text-display-sm font-bold` | stat grid |
| `candidate-sort-toggle.tsx` | track `bg-muted p-1 rounded-md flex gap-1`; buttons `text-meta px-3 py-1.5 rounded-sm`; active `bg-card text-primary-strong font-semibold shadow-control`; labels Name · Highest score · Newest | segmented control |
| `candidate-table.tsx` | section `rounded-2xl border bg-card overflow-hidden`; header row h2 "Candidates" + toggle; columns Candidate (avatar `size-9 rounded-full bg-primary-soft text-primary-strong` initials + name + note) · Answers ("{a} of {t}" + 6px bar `bg-border` / fill `bg-primary` width %) · Avg suggested (`text-title font-bold` + "/ 4", "—" when null; small "final {x}" line in `text-primary-strong` when `avg_final` differs) · Scoring jobs (`JobCountsChips`) · Last activity (`formatRelative`, "—") · Review (`Button` link `h-9 text-meta` → `/hr/candidates/{id}`, `aria-label="Review {name}"`); `th` style `text-caption uppercase tracking-[.04em] bg-surface-subtle`, rows `border-border-subtle` | table |
| `role-footnote.tsx` | `text-meta text-muted-foreground`: "Scores are suggestions — HR decides. Press Refresh to see newly scored answers." | footnote (reworded: no "Read first") |

Empty role (0 candidates) → table body row "No candidates for this role yet."

## Related Code Files
- Create: `apps/web/src/app/hr/(app)/roles/[roleId]/page.tsx` (`metadata.title = "Candidates"`, renders `<RoleCandidatesScreen/>`, reads `roleId` via `useParams` in the client root)
- Create: `apps/web/src/lib/hr-role-stats.ts`
- Create: `apps/web/src/components/hr/role/{role-candidates-screen,role-header,role-stat-cards,candidate-sort-toggle,candidate-table,role-footnote}.tsx`

## Implementation Steps
<!-- Updated: user request 2026-11-02 - inspect design + map colors to tokens -->
0. **Inspect + map colors first.** Open `HRDashboard.dc.html`, list every color in the part you're building, and map each one to its token with the [color map](phase-01-gate-and-hr-api-client-plumbing.md#design-color--token-map). Code uses token utilities only: no hex, `rgb(a)`, `hsl`, `bg-[#…]` or inline color styles. Pick by role where one value maps to several tokens. Expected tokens: background, card, border, border-subtle, surface-subtle, muted, muted-foreground, foreground, foreground-body, primary, primary-strong, primary-soft, primary-border, success-subtle/ink, neutral-subtle/ink, danger-subtle/ink, danger-border, warning-subtle/ink, warning-border, shadow-control.
1. `hr-role-stats.ts` (pure helpers).
2. Components top-down; wire data + Refresh button.
3. Responsive pass at 360 / 768 / 1440px.
4. `pnpm lint && pnpm typecheck && pnpm build`.

## Success Criteria
- [ ] Every color in this phase's UI traces to a token in the color map; `grep` finds no hex/rgb/hsl/arbitrary color in the files created here
- [ ] Layout matches `HRDashboard.dc.html` (spacing, chips, table) except the dropped button and "Read first"
- [ ] Stats equal the sums of the response (spot check against `GET /api/hr/roles/{id}/candidates` in devtools)
- [ ] Sorting: Highest puts nulls last; Newest by `last_activity_at`; Name restores API order
- [ ] Switching role updates URL and data; unknown role id → not-found card
- [ ] Refresh refetches without flashing a full-page loader and updates "Updated HH:MM"

## Risk Assessment
- Seeded data before the worker lands: all jobs queued, avg "—". Page must still look intentional (notes say "Scoring in progress").
- `Select` is the base-ui shadcn variant: check its API (`onValueChange`) in `components/ui/select.tsx` before wiring.
