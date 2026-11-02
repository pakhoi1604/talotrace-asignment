---
phase: 5
title: "Scoring jobs page"
status: completed
priority: P2
dependencies: [2]
---

# Phase 5: Scoring jobs page

## Overview
`/hr/jobs?status=` lists every scoring job with its status (brief: "The HR area shows the status of every job"). `?status=needs_person` is the "Needs a person" view with each reason. No artboard exists, so reuse the dashboard's table, chip and segmented-control recipes.

## Requirements
- Functional: filter chips All · Queued · Scored · Failed · Needs a person · Replaced, each with its count from `counts`; the URL carries the filter (`router.replace`, shareable); row → candidate review; failed rows get an inline **Retry**; Refresh button (no auto-refresh).
- Non-functional: same table semantics and responsive behaviour as phase 3; tokens only.

## Architecture

### Data
<!-- Updated: Validation Session 1 - polling replaced by Refresh button -->
`useHrResource(() => listJobs(status), [status])`; `RefreshButton` in the heading row.
- Filter "Queued" requests `queued` and `running` together? The API filters one status at a time. → "Queued" chip calls `listJobs("queued")`, and its count shows `counts.queued + counts.running`. Running jobs appear under "All". Note this in the footnote ("Jobs being scored right now show under All."). Do not add API params.
- Unknown `status` in the URL → treat as All (don't send it; avoids a 422).

### Components (`src/components/hr/jobs/`)
| File | Responsibility |
|---|---|
| `jobs-screen.tsx` | client root: reads `status` (`useSearchParams`, in Suspense), data, retry handler (reuse `retryJob` + 409 map + refetch) |
| `jobs-filter-chips.tsx` | segmented track as in phase 3; each option "{label} {count}" with count pill; `aria-pressed` |
| `jobs-table.tsx` | columns: Status (`JobStatusChip`) · Candidate (name, link to review) · Role · Question (`question_id`) + answer kind icon (`AlignLeft` / `Mic`) · Detail (needs_person → `needs_person_reason`; failed → `last_error` truncated with `title`; queued → "attempt {n}"; else "—") · Updated (`formatRelative`) · Action (failed → Retry button `h-9`; else "Review" link) |
| `jobs-page-heading.tsx` | h1 "Scoring jobs" or "Needs a person" (from filter) + `RefreshButton` + one-line description: "Every answer gets one scoring job. Failed jobs never count as a low score — retry them here or on the candidate page." |

Empty state per filter: "No {label} jobs." (needs_person: "Nothing needs a person right now.").

## Related Code Files
- Create: `apps/web/src/app/hr/(app)/jobs/page.tsx` (`metadata.title = "Scoring jobs"`, `<Suspense><JobsScreen/></Suspense>`)
- Create: `apps/web/src/components/hr/jobs/{jobs-screen,jobs-filter-chips,jobs-table,jobs-page-heading}.tsx`

## Implementation Steps
<!-- Updated: user request 2026-11-02 - inspect design + map colors to tokens -->
0. **Inspect + map colors first.** Open `HRDashboard.dc.html` (no jobs artboard exists, so reuse its table, chip and segmented-control recipes), list every color in the part you're building, and map each one to its token with the [color map](phase-01-gate-and-hr-api-client-plumbing.md#design-color--token-map). Code uses token utilities only: no hex, `rgb(a)`, `hsl`, `bg-[#…]` or inline color styles. Pick by role where one value maps to several tokens. Expected tokens: same set as phase 3 (table, chips, segmented control) + danger-ink for error text.
1. Page + screen with filter from URL.
2. Table + chips + empty states.
3. Inline retry.
4. `pnpm lint && pnpm typecheck && pnpm build`; browser check of every filter.

## Success Criteria
- [ ] Every color in this phase's UI traces to a token in the color map; `grep` finds no hex/rgb/hsl/arbitrary color in the files created here
- [ ] Every filter shows the right rows and counts; URL reflects the filter; nav highlights "Needs a person" only for that filter
- [ ] Needs-a-person rows show their reason; failed rows show the error and Retry works
- [ ] No score columns on this page (JobListItem has none)

## Risk Assessment
- Jobs list size: data pack ≈ 35 jobs, no pagination needed (API has none). Note it in "not built" if lists grow.
