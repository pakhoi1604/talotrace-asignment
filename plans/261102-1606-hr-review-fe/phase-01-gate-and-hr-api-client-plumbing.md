---
phase: 1
title: "Gate + HR API client plumbing"
status: completed
priority: P1
dependencies: []
---

# Phase 1: Gate + HR API client plumbing

## Overview
Check both blockers, then add everything the HR pages share: typed HR client, 204/JSON handling in `api-client.ts`, auth redirect (proxy + 401 handling), a small data hook with manual reload, friendly error copy, formatting helpers, the shared status/score components, a Refresh button and the extracted brand mark.

<!-- Updated: Validation Session 1 - gate accepts done|completed; HR doc must be on main -->
## Step 0: Gate (stop with `Status: BLOCKED` if any check fails)
```bash
git fetch && git switch main && git pull
grep -c "^### .*/api/hr/" docs/api-doc.md          # expect 11 (HR API merged to main)
grep -nE "^status: (done|completed)$" plans/261102-1529-design-tokens-candidate-interview-fe/plan.md   # satisfied at 2a50566
grep -n "success\|warning\|danger\|info\|neutral" apps/web/src/components/ui/badge.tsx  # tokens phase landed (verified)
```
Do not branch from `feat/hr-review-api`. Wait until it's merged to `main`.
Then create the worktree: `git worktree add ../talotrace-hr-review-fe -b feat/hr-review-fe main`.
Re-read the HR sections of `docs/api-doc.md` and compare with `apps/web/src/lib/api-types.ts`. If types are missing or drift, fix **`api-types.ts` only** (FE file) to match the doc. Never read `apps/api` to infer shapes.

<!-- Updated: user request 2026-11-02 - design color inspection + token map -->
## Design color → token map
Source: every color in `Main.dc.html`, `HRDashboard.dc.html` and `CandidateReview.dc.html`, looked up in `apps/web/src/app/globals.css` `:root` on `main` (`2a50566`). Tailwind utility = `bg-` / `text-` / `border-` + the token name without `--`.

### Step 1a: re-inspect before coding (5 min)
```bash
cd docs/design
grep -ohiE '#[0-9a-f]{6}\b|rgba?\([^)]*\)' "— HR sign-in-html/Main.dc.html" "hr roles [id] — Candidates-html/HRDashboard.dc.html" "hr candidates [id] — Review-html/CandidateReview.dc.html" | tr 'A-F' 'a-f' | sort -u
```
Each value must appear in the table below. A new value (artboards changed) → find its token in `globals.css`. If none exists, use the nearest token and list it in the report. Never add a token or a hex value.

### Map (hex is for lookup only; code uses the token)
| Design value | Token | Use for (pick by role when a value has several tokens) |
|---|---|---|
| `#FFFFFF` | `card` · `primary-foreground` · `secondary` | card/form/header/table bg → `bg-card`; text/icons on blue → `text-primary-foreground`; secondary button bg → `bg-secondary` |
| `#F8FAFF` | `background` | page bg, sign-in form panel |
| `#F8FAFC` | `surface-subtle` | review side panel, table `th` bg |
| `#F1F5F9` | `muted` | segmented-control track, audio panel bg |
| `#0F172A` | `foreground` | primary text, headings, numbers |
| `#1E293B` | `foreground-soft` | sign-in form labels |
| `#334155` | `foreground-body` · `neutral-ink` | answer body, inactive nav link, "x of 6" → `text-foreground-body`; queued chip text → `text-neutral-ink` |
| `#475569` | `muted-foreground` | meta, helper, `th` text, stat labels, sign-out link |
| `#E2E8F0` | `border` · `neutral-subtle` | card/header/table borders, progress track → `border-border` / `bg-border`; queued chip bg → `bg-neutral-subtle` |
| `#EEF2F7` | `border-subtle` | table row dividers |
| `#CBD5E1` | `input` | input/select/textarea/score-tile borders |
| `#2563EB` | `primary` · `ring` | primary buttons, logo tile, progress fill, checked score tile border, focus outline |
| `#1D4ED8` | `primary-strong` | links, active nav text, eyebrow "Question n of 6", secondary button text, sign-in brand panel bg, avatar text |
| `#1E3A8A` | `primary-deep` | link hover |
| `#1E40AF` | `primary-ink` | "HR override" chip text, HR reason label, "Submitted 2×" pill text |
| `#93C5FD` | `primary-muted` | card border while the override form is open |
| `#BFDBFE` | `primary-border` | secondary button border, override form border, sign-in footer text |
| `#DBEAFE` | `primary-subtle` | header avatar bg, "HR override" chip bg, sign-in lead text, focus halo (`shadow-focus`) |
| `#EFF6FF` | `primary-soft` | active nav bg, table avatar bg, checked score tile bg, HR reason box, "Submitted 2×" pill bg |
| `#DCFCE7` / `#166534` | `success-subtle` / `success-ink` | "Scored" chip (Badge `success`) |
| `#FEF3C7` / `#92400E` | `warning-subtle` / `warning-ink` | "Needs a person" chip, "Mock auth" / "Mocked sign-in" / "Transcription not built" badges (Badge `warning`), nav count pill, "Why a person is needed" label |
| `#FCD34D` | `warning-border-strong` | border of the sign-in "Mocked sign-in — demo only" badge (`border border-warning-border-strong`) |
| `#FDE68A` | `warning-border` | needs-a-person card border + side-panel border, needs-a-person stat card border |
| `#FFFBEB` | `warning-soft` | needs-a-person side panel bg |
| `#78350F` | `warning-ink-strong` | (artboard `<mark>` text: highlight is dropped, unused) |
| `#FEE2E2` / `#991B1B` | `danger-subtle` / `danger-ink` | "Failed" chip (Badge `danger`), "No score yet" title + icon |
| `#FECACA` | `danger-border` | failed card border + side-panel border, failed stat card border |
| `#FEF2F2` | `danger-soft` | failed side panel bg |
| `#7F1D1D` | `danger-ink-strong` | "Last attempt … · job #id" line |
| `#B91C1C` | `danger` | "(required)" marker on the override reason |
| `rgba(255,255,255,0.16)` | `primary-foreground` + opacity | sign-in feature icon bubbles → `bg-primary-foreground/16` |
| `0 1px 2px rgba(15,23,42,.04), 0 8px 24px rgba(37,99,235,.06)` | `shadow-card-raised` | sign-in form card |
| `0 1px 2px rgba(15,23,42,.08)` | `shadow-control` | active segmented-control thumb |
| `0 0 0 3px #DBEAFE` | `shadow-focus` | review card with the override form open |

Status → Badge variant (from the map): scored → `success`, queued/running → `neutral`, failed → `danger`, needs_person → `warning`, HR override/accepted → `info`, superseded → `neutral`.

## Contract preview (from the HR API plan; the doc wins)
- Auth: httpOnly `hr_session` cookie (MOCK sign-in, one `.env` account). Any auth failure → 401 `invalid or missing hr session`.
- `POST /api/hr/session` `{email,password}` → 200 `{email, expires_at}` · 401 `invalid email or password` · 503 `hr sign-in is not configured` · 415 · 422.
- `GET /api/hr/session` → 200 `{email, expires_at}` / 401. `DELETE /api/hr/session` → **204, no body**.
- `GET /api/hr/roles` → `{roles:[{id,title,candidate_count,job_counts}]}`.
- `GET /api/hr/roles/{id}/candidates` → `{role, total_questions, candidates:[{id,name,answered_count,total_questions,avg_suggested,avg_final,job_counts,last_activity_at}]}`.
- `GET /api/hr/candidates/{id}` → `CandidateReview` (questions[] with `answer | null`, `job`, `decisions` newest first, `earlier_submissions`, `final_score`, `final_source`).
- `GET /api/hr/jobs?status=` → `{counts (6 statuses), jobs:[JobListItem]}`; default excludes `superseded`.
- `GET /api/hr/answers/{id}/audio` → bytes (used as `<audio src>`, never fetched by JS).
- `POST …/override` `{score, reason}` · `POST …/accept` `{score}` → 201/200 `DecisionView`. `POST /api/hr/jobs/{id}/retry` `{}` → 200 `JobView`. All HR POSTs need `Content-Type: application/json`.
- 409 details: `answer has been replaced by a newer submission` · `no suggested score to accept` · `needs a person: use override with a reason` · `suggested score has changed, reload and try again` · `another decision for this answer was just saved, reload and try again` · `only failed jobs can be retried`. 422: `reason: must not be blank` · `reason: must be at most 2000 characters`.

## Requirements
- Functional: one typed function per HR endpoint; 401 from any HR call redirects to sign-in with `next`; 204 handled; manual reload (no timers).
- Non-functional: `cache: "no-store"` on all HR GETs; `credentials` default (same-origin) is enough; no raw hex; modules < 200 lines.

## Architecture

### `src/lib/api-client.ts` (shared, minimal change)
```ts
if (res.status === 204) return undefined as T;   // DELETE /api/hr/session
```
Non-204 behaviour unchanged, so the candidate client is unaffected.

### `src/lib/hr-api.ts` (new)
```ts
const json = (body: unknown): RequestInit => ({
  method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
});
const get = <T>(path: `/api/${string}`) => apiFetch<T>(path, { cache: "no-store" });

export const signIn = (email: string, password: string) => apiFetch<HrSession>("/api/hr/session", json({ email, password }));
export const getSession = () => get<HrSession>("/api/hr/session");
export const signOut = () => apiFetch<void>("/api/hr/session", { method: "DELETE" });
export const listRoles = () => get<RoleList>("/api/hr/roles");
export const getRoleCandidates = (roleId: number | string) => get<RoleCandidates>(`/api/hr/roles/${encodeURIComponent(roleId)}/candidates`);
export const getCandidateReview = (id: string) => get<CandidateReview>(`/api/hr/candidates/${encodeURIComponent(id)}`);
export const listJobs = (status?: JobStatus) => get<JobList>(`/api/hr/jobs${status ? `?status=${status}` : ""}`);
export const overrideScore = (answerId: string, score: number, reason: string) => apiFetch<DecisionView>(`/api/hr/answers/${encodeURIComponent(answerId)}/override`, json({ score, reason }));
export const acceptScore = (answerId: string, score: number) => apiFetch<DecisionView>(`/api/hr/answers/${encodeURIComponent(answerId)}/accept`, json({ score }));
export const retryJob = (jobId: number) => apiFetch<JobView>(`/api/hr/jobs/${jobId}/retry`, json({}));
```
Names follow `api-types.ts` as written by the API plan (`RoleList` may be named differently: use the doc's name).

### `src/proxy.ts` (new, Next 16 proxy = former middleware)
```ts
export function proxy(req: NextRequest) {
  if (req.cookies.has("hr_session")) return NextResponse.next();
  const url = new URL("/hr/sign-in", req.url);
  url.searchParams.set("next", req.nextUrl.pathname + req.nextUrl.search);
  return NextResponse.redirect(url);
}
export const config = { matcher: ["/hr", "/hr/((?!sign-in).*)"] };
```
Presence check only. The API validates the session, and the client handles 401 too. Confirm the Next 16.4 proxy API (file name, export name) with `ck:docs-seeker` before writing.

### `src/lib/hr-auth-redirect.ts` (new)
- `safeNext(raw: string | null): string`: returns `raw` only if it starts with `/hr/` and not `//`, else `/hr`. Stops open redirects.
- `useHrUnauthorizedRedirect()`: returns `(err) => boolean`. On `ApiRequestError` 401 → `router.replace('/hr/sign-in?next=' + encodeURIComponent(pathname + search))`, returns true.

<!-- Updated: Validation Session 1 - polling dropped; manual reload + Refresh button -->
### `src/hooks/use-hr-resource.ts` (new)
```ts
function useHrResource<T>(load: () => Promise<T>, deps: unknown[])
  : { data?: T; error?: string; loading: boolean; refreshing: boolean; loadedAt?: Date; reload: () => Promise<void> }
```
- Fetch on mount and when `deps` change; ignore stale responses (request counter).
- `reload()` keeps the old data visible and sets `refreshing` (no full-page loader). It's used by the Refresh button and after every action.
- 401 → redirect helper; other errors → `toHrMessage(err)`.
- No timers or polling (user decision).

### `src/components/hr/refresh-button.tsx` (new)
`Button variant="secondary" size="sm"` with lucide `RotateCw` (spins while `refreshing`, `motion-safe:animate-spin`) + "Refresh"; next to it `text-meta text-muted-foreground` "Updated {formatTime(loadedAt)}". `aria-live="polite"` on the timestamp.

### `src/components/brand-mark.tsx` (new, shared with the candidate area)
Extract the logo tile from `interview/interview-header.tsx:20`: `<BrandMark size="sm" | "lg" tone="primary" | "inverse" />`
- `sm` + `primary` = `size-8 rounded-sm bg-primary` + `text-primary-foreground` `Check` (candidate header, HR header)
- `lg` + `inverse` = `size-10 rounded-md bg-card` + `text-primary-strong` `Check` (sign-in brand panel)
Replace the inline tile in `interview-header.tsx` with `<BrandMark size="sm" />`. It must render pixel-identical (same classes).

### `src/lib/hr-error-messages.ts` (new)
`toHrMessage(err: unknown): string`. Look up by exact `detail`, then status, then raw `detail`:
| `detail` / case | HR sees |
|---|---|
| `invalid email or password` | "Email or password is incorrect." |
| `hr sign-in is not configured` | "HR sign-in isn't set up. Set HR_EMAIL and HR_PASSWORD in apps/api/.env." |
| `answer has been replaced by a newer submission` | "The candidate sent a newer answer. We've reloaded it, so please review again." |
| `no suggested score to accept` | "There's no suggested score to accept yet." |
| `needs a person: use override with a reason` | "This answer needs a person. Use Override and give a reason." |
| `suggested score has changed, reload and try again` | "The suggested score changed. We've reloaded the latest." |
| `another decision for this answer was just saved, reload and try again` | "Someone just saved a decision for this answer. We've reloaded it." |
| `only failed jobs can be retried` | "This job is no longer failed. We've reloaded its status." |
| `reason: must not be blank` | "Please give a reason for the override." |
| `reason: must be at most 2000 characters` | "Keep the reason under 2,000 characters." |
| 404 | "Not found. It may have been removed." |
| network / `TypeError` | "Couldn't reach the server. Check that the API is running." |
Exported `RELOAD_ON_409 = true`: callers refetch after any 409.

### `src/lib/hr-format.ts` (new)
- Reuse `formatTime` from `src/lib/format-time.ts` (import it, don't redefine it). Add `formatDateTime(iso)` → `2 Nov, 09:41`.
- `formatRelative(iso, now)` → "just now", "12 min ago", "3 h ago", "Yesterday", else date (`Intl.RelativeTimeFormat` not needed: simple buckets).
- `formatAvg(n | null)` → `"3.2"` / `"—"`; `formatBytes(n)` → `"1.4 MB"`; `audioFormatLabel(contentType)` → `"M4A"`, `"MP3"`, …
- `initials(name)` → `"LT"`.
- `displayStatus(status)`: `running` → `queued`; others unchanged.

### Shared HR components (`src/components/hr/`)
| File | Responsibility | Design ref |
|---|---|---|
| `job-status-chip.tsx` | `Badge` pill + dot. scored → `success`, queued/running → `neutral` ("Queued"), failed → `danger`, needs_person → `warning` ("Needs a person"), superseded → `neutral` ("Replaced"). Prop `count?` renders "4 scored" style | `.chip .c-*` |
| `hr-override-chip.tsx` | `Badge variant="info"` "HR override" | `.c-hr` |
| `score-figure.tsx` | big number `text-score font-bold` + "/ 4 {label}"; `tone="hr"` → `text-primary-strong`; optional struck-through "{n} suggested" | `.big` |
| `job-counts-chips.tsx` | renders non-zero chips from `JobCounts` (scored always, others when > 0), queued = queued + running | table "Scoring jobs" cell |

## Related Code Files
- Modify: `apps/web/src/lib/api-client.ts` (204), `apps/web/src/lib/api-types.ts` (only if it drifts from the doc)
- Create: `apps/web/src/lib/hr-api.ts`, `hr-auth-redirect.ts`, `hr-error-messages.ts`, `hr-format.ts`
- Create: `apps/web/src/hooks/use-hr-resource.ts`
- Create: `apps/web/src/proxy.ts`
- Create: `apps/web/src/components/hr/{job-status-chip,hr-override-chip,score-figure,job-counts-chips,refresh-button}.tsx`
- Create: `apps/web/src/components/brand-mark.tsx`
- Modify: `apps/web/src/components/interview/interview-header.tsx` (use `BrandMark`, no visual change)

## Implementation Steps
1. Step 0 gate + worktree.
2. Step 1a: re-run the color inspection; confirm every value is in the map (record the result in the phase report).
3. Type check against the doc; patch `api-types.ts` if needed.
3. `api-client.ts` 204 branch.
4. `hr-api.ts`, error map, format helpers (import `formatTime`), redirect helper, hook.
5. `proxy.ts` (verify Next 16 proxy API first).
6. Shared components + `brand-mark.tsx`; swap it into `interview-header.tsx`, check `/i/<token>` looks unchanged.
7. `pnpm lint && pnpm typecheck`.

## Success Criteria
- [ ] Gate checks recorded in the phase report
- [ ] Color inspection re-run: every artboard color is in the map (or the gap is reported); shared components use only mapped tokens, no hex
- [ ] Every HR route in the doc has one function in `hr-api.ts`; every documented HR 409/422 `detail` has a row in `hr-error-messages.ts`
- [ ] `apiFetch` on a 204 returns without throwing
- [ ] `/hr/roles/1` with no cookie → 307 to `/hr/sign-in?next=%2Fhr%2Froles%2F1`; `/hr/sign-in` itself is not redirected
- [ ] `pnpm lint`, `pnpm typecheck` green

## Risk Assessment
- Next 16 proxy naming/matcher syntax may differ from the snippet → check docs first; fallback is a 401 client redirect only (still correct, just a flash).
- `cacheComponents: true`: client components that read `useSearchParams` need a `<Suspense>` boundary or the build fails → wrap in each page (phase 2–5).
- No auto-refresh: HR sees stale "Queued" until they press Refresh. This is the user's choice; the button shows when data was loaded.
- Brand-mark extraction touches candidate code: keep the exact class list, so it's a visual no-op.
