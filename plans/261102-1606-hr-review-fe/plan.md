---
title: "HR review FE pages"
description: "Build the HR area in apps/web from docs/design (sign-in, candidates per role, candidate review, scoring jobs) on top of the HR API documented in docs/api-doc.md. Frontend only."
status: completed
priority: P1
branch: feat/hr-review-fe
tags: [frontend, hr]
blockedBy: [261102-1531-hr-review-api, 261102-1529-design-tokens-candidate-interview-fe]
blocks: []
created: 2026-11-02
---

# HR review FE pages

Design source: `docs/design/— HR sign-in-html/Main.dc.html`, `docs/design/hr roles [id] — Candidates-html/HRDashboard.dc.html`, `docs/design/hr candidates [id] — Review-html/CandidateReview.dc.html` (reference mockups, not production code). Contract source: **`docs/api-doc.md` HR sections only** (AGENTS.md rule 2). Tokens and primitives: `261102-1529-design-tokens-candidate-interview-fe` phase 1.

## Blockers (both resolved — plan is unblocked)
<!-- Updated: 2026-11-02 - both blockers resolved; plan unblocked -->
1. **RESOLVED 2026-11-02: `docs/api-doc.md` on `main` has the HR section**: all 11 `/api/hr/*` routes present (`session` ×3, `roles` ×2, `candidates` ×1, `jobs` ×2, `answers` ×3), written by `261102-1531-hr-review-api` (status `done`, merged to `main` at `c22921a`).
2. **RESOLVED 2026-11-02: `261102-1529-design-tokens-candidate-interview-fe` is finished** (status `done`, merged to `main` at `2a50566`). This plan reuses its tokens, Inter font, Badge/Button/Alert variants, `globals.css`, `format-time.ts`, `candidate-api.ts` pattern and `next.config.ts` headers.

Phase 1 step 0 checks both. If either fails → `Status: BLOCKED`, stop. Do not write HR shapes from backend code or from the HR API plan's drafts. The contract notes in the phases below are a **planning preview** of what the API plan promises. The doc wins on any difference.

## Scope (hard)
**Frontend only.** Touch `apps/web/**`, `docs/design-guidelines.md`, `docs/architecture.md` (frontend section), `README.md` (HR pages section). **Never** edit `apps/api/**`, the HR endpoint sections of `docs/api-doc.md`, or backend plan files. If the design needs something the API lacks, adapt the UI.
No global theme token changes (AGENTS.md rule 9). If a needed token is missing, use the nearest existing token and list it in the report. Don't add it.

<!-- Updated: user request 2026-11-02 - design inspection + color→token map, no hex -->
## Colors: design tokens only, never hex (hard)
Before building any component, the implementer **inspects the artboard it reproduces** (read the inline `style` attributes and the `<helmet><style>` block) and maps every color to a token using the **[Design color → token map](phase-01-gate-and-hr-api-client-plumbing.md#design-color--token-map)** in phase 1. Rules:
- No hex, `rgb()`, `rgba()`, `hsl()`, arbitrary color classes (`bg-[#…]`, `text-[rgb(…)]`) or inline `style={{ color/background/border… }}` in HR code. Only token utilities (`bg-primary-soft`, `text-warning-ink`, `border-danger-border`, `shadow-card-raised`, …) or opacity modifiers on tokens (`bg-primary-foreground/16`).
- Where one hex maps to several tokens, pick by **role** (the map's "Use for" column), not by value.
- Each component phase (2–5) starts with an "Inspect + map" step and lists the tokens it uses. Phase 6 enforces it with grep.
- Inspection done at planning time (2026-11-02): **33 distinct hex values + 4 rgba values across the 3 HR artboards, all covered by existing tokens. 0 missing, so no token changes are needed.** (`#318` in the review artboard is the job number text, not a color.)

## Branch
After both blockers merge: worktree from `main` on `feat/hr-review-fe` (AGENTS.md rule 10). Commit, push, remove the worktree at the end.

## Decisions (locked with user, 2026-11-02)
| Area | Decision |
|---|---|
| Data fetching | **Client-side.** HR pages are client components calling `/api/*` through the existing rewrite (the browser sends the httpOnly `hr_session` cookie). Any 401 → `/hr/sign-in?next=<path>`. `src/proxy.ts` redirects early when there's no `hr_session` cookie (presence only, the backend decides validity) |
| Jobs page | **Build `/hr/jobs`** with status filter chips. Nav "Needs a person" = `/hr/jobs?status=needs_person` (reason column). Nav "Scoring jobs" = `/hr/jobs` |
| Candidate sort | **Client-side toggle: Name (default, API order) · Highest score · Newest.** No "Read first" (brief optional extra) |
| Backend | None. FE consumes the HR API as documented |
| Refresh | **Manual "Refresh" button** on the role, review and jobs pages (shows "Updated HH:MM"). No timers or polling (validation 2026-11-02) |
| Reuse | `hr-format.ts` imports `formatTime` from `src/lib/format-time.ts`. The logo tile is extracted to `src/components/brand-mark.tsx` and used by `interview-header.tsx` and the HR pages (validation 2026-11-02) |
| Override | Available on **any answered question** (queued, failed, scored, needs a person, decided). Accept stays `scored`-only, Retry `failed`-only (validation 2026-11-02) |
| Grading guide | Collapsed `<details>` with the rubric 1–4 under each question on the review page (not in the mockup; validation 2026-11-02) |
| Start point | Wait until the HR API is merged to `main`, then branch `feat/hr-review-fe` from `main` (validation 2026-11-02) |

## Design → API reconciliation (defaults chosen by planner; the API plan is fixed)
| Mockup element | What we build | Why |
|---|---|---|
| Sign-in "Password · Any value works", prefilled values | Empty fields; hint "Demo account is in `apps/api/.env`"; keep "Mocked sign-in — demo only" badge | API accepts only the `.env` account (401 otherwise) |
| "Load data pack answers" button | Dropped. Empty role state says "Run `make seed` to load the data pack" | No endpoint; API plan lists it as not built |
| Q4 needs-a-person with "2 / 4 suggested" + "Accept 2" | Reason panel + **Override only**. Show a suggested score only if the API returns one | Accept on `needs_person` → 409 `needs a person: use override with a reason` |
| `<mark>` highlight of the injection sentence | Dropped; answer shown as plain text | API doesn't return the span |
| Audio "answer-q6.m4a · 1:42" + custom player + "Mocked transcript" | Native `<audio controls preload="none">` + "Audio answer arrived · {format} · {size}" + label **"Transcription not built"** | API returns `{content_type, size_bytes, url}` only; no transcript exists (rule 5: label it) |
| Job status `running` | Shown as "Queued" chip | API doc: UI maps `running` to the brief's four statuses |
| "Needs a person (3)" nav count | Sum of `job_counts.needs_person` over `GET /api/hr/roles` | Cheap, one call, already in the header |

## Phases
| # | Phase | Status | Depends |
|---|---|---|---|
| 1 | [Gate + HR API client plumbing](phase-01-gate-and-hr-api-client-plumbing.md) | completed | blockers |
| 2 | [Sign-in + HR shell](phase-02-sign-in-and-hr-shell.md) | completed | 1 |
| 3 | [Candidates per role](phase-03-candidates-per-role-page.md) | completed | 2 |
| 4 | [Candidate review](phase-04-candidate-review-page.md) | completed | 2 |
| 5 | [Scoring jobs page](phase-05-scoring-jobs-page.md) | completed | 2 |
| 6 | [Verification + docs](phase-06-verification-and-docs.md) | completed | 3, 4, 5 |

Phases 3/4/5 touch separate folders and could run in parallel. Shared pieces (`job-status-chip`, `score-figure`, `job-counts-chips`, `refresh-button`, `brand-mark`, format helpers) are created in phase 1 so they don't collide.

## Routes
```
/hr/sign-in                     public sign-in (mock)
/hr                             → first role (client redirect)
/hr/roles/[roleId]              candidates for a role
/hr/candidates/[candidateId]    candidate review (answers, scores, override/accept/retry)
/hr/jobs?status=                scoring jobs (+ needs-a-person view)
```

## Acceptance criteria
- [ ] Phase 1 gate passed: HR doc sections exist; `api-types.ts` HR types match the doc field by field
- [ ] Sign-in with the `.env` account → `/hr` → first role; wrong creds → inline "Email or password is incorrect"; MOCK label visible on sign-in and in the header
- [ ] No `hr_session` cookie on any `/hr/*` page except sign-in → redirected to `/hr/sign-in?next=…`; expired/revoked session (API 401) → same redirect; `next` only accepts paths that start with `/hr/`
- [ ] Sign out → `DELETE /api/hr/session` (204, body not parsed) → sign-in page
- [ ] Role page: role switcher, 6 stat cards, candidate table (answered x of N, avg suggested, job chips, last activity, Review link), Name/Highest/Newest sort
- [ ] Review page per question: status chip; text or audio answer; "Submitted N× · this one counts" + earlier submissions with their HR decisions; suggested score + reason; needs-a-person reason; failed → "No score yet" + last error + attempts + **Retry scoring**; final score with HR override + reason + who/when
- [ ] Override: score 1–4 + reason required (client check, then API); Accept only on `scored` without an HR decision; every documented 409 shows friendly copy and refetches
- [ ] A failed job never shows a score anywhere (no number in the score slot; UI renders only what the API returns)
- [ ] Jobs page: status filter chips with counts; needs-a-person view shows the reason; each row links to the candidate review
- [ ] Role, review and jobs pages have a "Refresh" button that refetches without a full-page loader and shows "Updated HH:MM"; no timers
- [ ] Logo tile comes from the shared `brand-mark.tsx` (candidate header still renders the same); `formatTime` isn't duplicated
- [ ] Every artboard color is rendered through the token named in the phase-1 color map; zero hex / `rgb(a)` / `hsl` / arbitrary color classes / inline color styles in `apps/web/src/app/hr`, `src/components/hr`, `src/components/brand-mark.tsx` (phase 6 grep); no global token edits; HR pages `noindex`
- [ ] Zero files changed under `apps/api/`; HR sections of `docs/api-doc.md` unchanged (`git diff --stat main` check)
- [ ] `make lint && make test` green; `pnpm build` succeeds; browser smoke of all 5 routes done

## Out of scope
Backend changes of any kind · "Read first" ordering · "Load data pack" button · audio transcription / mocked transcript · injection-sentence highlight · HR-agreement report · multi-user HR · dark mode · FE unit-test framework.

## Cross-plan
- `261102-1529-design-tokens-candidate-interview-fe`: frontmatter `blocks: [261102-1606-hr-review-fe]` added. No content change.
- `261102-1531-hr-review-api`: **not edited** (user rule: FE plan must not touch BE files). The link is one-way, recorded here only. Its hand-off notes are honoured: `request()` handles 204, HR `POST`s send `Content-Type: application/json`, retry body `{}`.
- `261102-1549-llm-scoring-worker`: no file overlap. Until it lands, every seeded job shows "Queued", which is honest. The review page must render it cleanly.

## Open questions
None blocking. Shared files: phase 1 edits `src/lib/api-client.ts` (204 branch) and `src/components/interview/interview-header.tsx` (uses `BrandMark`), both from the candidate plan. Neither change alters candidate behaviour or visuals.

## Validation Log

### Session 1 — 2026-11-02
Trigger: post-plan validation, before the HR API lands.

#### Verification Results
- Claims checked: 24
- Verified: 20 | Failed: 2 | Unverified: 2
- Tier: Full (Fact Checker + Contract Verifier + Dependency/Pattern checks)
- Evidence: tokens `--shadow-focus --radius-tab --text-score --container-app --color-primary-ink --color-warning-soft --color-danger-ink-strong --color-surface-subtle` in `apps/web/src/app/globals.css`; Badge `success/warning/danger/info/neutral` (`ui/badge.tsx:21-29`); Alert `success` (`ui/alert.tsx:13`); Button sizes `xl`, `cta`; `ui/select.tsx` = `@base-ui/react/select`; `/usr/bin/sqlite3`; candidate FE merged (`2a50566`, plan status `done`); `docs/api-doc.md` has no `/api/hr/*` sections yet
- Failures: (1) phase-1 gate grepped `completed`, but the plan says `done` → fixed; (2) `formatTime` duplicated `src/lib/format-time.ts`, and the logo tile duplicated `interview/interview-header.tsx:20` → reuse/extract
- Unverified: Next 16.4 `proxy.ts` export/matcher (node_modules scouting blocked; phase 1 checks docs first); audio `Range` through the `/api` rewrite (phase 4/6 smoke)

#### Questions & answers
1. Gate status check → accept `done` or `completed`; blocker 2 marked resolved
2. Reuse → import `formatTime`; extract `brand-mark.tsx` and use it in the candidate header too
3. Auto-refresh → **dropped**; manual Refresh button instead
4. Override on queued/failed → yes, any answered question
5. Grading guide → keep, collapsed
6. Start point → wait for the HR API on `main`

#### Propagation
- `plan.md`: blockers, decisions table (5 rows), acceptance criteria (refresh, reuse), open questions
- `phase-01`: gate grep, hook without polling, `refresh-button.tsx`, `brand-mark.tsx` + `interview-header.tsx` edit, `hr-format.ts` imports `formatTime`
- `phase-02`: header + sign-in use `BrandMark`
- `phase-03`/`04`/`05`: polling → Refresh button; footnote copy; success criteria
- `phase-06`: smoke step uses Refresh; scope guard allows the one candidate-header edit

#### Whole-Plan Consistency Sweep
- Files reread: plan.md, phase-01 … phase-06
- Decision deltas checked: 6 (gate status, start point, reuse formatTime, brand-mark extraction, polling → Refresh, override everywhere + grading guide)
- Searched: `poll`, `10 s`, `auto-refresh`, `hasPendingJobs`, `visibilityState`, `completed` gate, `logo tile`, `formatTime(iso)`, `four checks`
- Reconciled stale references: 4 (phase-03 step 2 "polling", phase-06 risk "accept/polling", plan.md shared-component names, phase-06 "four checks")
- Unresolved contradictions: 0

### Session 2 — 2026-11-02 (user request: inspect design, map colors to tokens, no hex)
- Inspected `Main.dc.html`, `HRDashboard.dc.html` and `CandidateReview.dc.html`: 33 distinct hex + 4 rgba values. Every one maps to an existing token in `globals.css` (`main` @ `2a50566`). 0 missing, so no token change is needed (rule 9 holds).
- Added: plan.md "Colors: design tokens only, never hex" section + acceptance criterion; phase-01 "Design color → token map" (role-based table, re-inspection step 1a); phases 2–5 step 0 "Inspect + map colors first" + a success criterion; phase-06 grep widened to hex/rgb(a)/hsl/arbitrary color classes/inline color styles + `brand-mark.tsx`, and the map documented in `docs/design-guidelines.md`.
- Fixed from the inspection: sign-in "Mocked sign-in" badge gets its `warning-border-strong` border; nav inactive link = `text-foreground-body`; brand mark check icon = `text-primary-foreground` (was "white"); removed the `bg-white/15` fallback.

#### Whole-Plan Consistency Sweep
- Files reread/searched: plan.md, phase-01 … phase-06 for `white`, `black`, `rgba`, `#…`, `bg-[`, `raw hex`
- Reconciled: 3 (`bg-white/15` fallback, "white `Check`", "four checks"/hex-only guard wording)
- Unresolved contradictions: 0

### Session 3 — 2026-11-02 (blocker re-check, `/ck:plan --update`)
- Blocker 1 verified on `main`: `git log main` shows `c22921a merge: HR review API (feat/hr-review-api)`; `261102-1531-hr-review-api` plan status `done`; `docs/api-doc.md` on `main` documents all 11 `/api/hr/*` routes (POST/GET/DELETE `session`, GET `roles`, GET `roles/{id}/candidates`, GET `candidates/{id}`, GET `jobs`, GET `answers/{id}/audio`, POST `answers/{id}/override`, POST `answers/{id}/accept`, POST `jobs/{id}/retry`). → **RESOLVED**
- Blocker 2 still resolved (`2a50566`, plan `done`). `ck plan status` confirms both `blockedBy` plans `[OK] done` → effective status `pending`.
- Plan status `blocked` → `pending`. Branch `feat/hr-review-fe` can now be cut from `main` per AGENTS.md rule 10.
