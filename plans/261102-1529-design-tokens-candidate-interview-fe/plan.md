---
title: "Design tokens + candidate interview FE"
description: "Turn the docs/design mockups into a global token set (Tailwind v4 + shadcn theme), then build the candidate interview page at /i/[token] on top of the candidate API."
status: done
priority: P1
branch: feat/candidate-interview-fe
tags: [frontend, design-system, candidate]
blockedBy: [261102-1509-candidate-api-db-seed]
blocks: [261102-1606-hr-review-fe]
created: 2026-11-02
---

# Design tokens + candidate interview FE

Design source: `docs/design/` (4 artboards, reference mockups, not production code). Contract source: `docs/api-doc.md`.
**HR pages are out of scope.** Tokens are extracted from all 4 artboards so the HR plan can reuse them, but only candidate UI is built here.

## Blocker (resolved 2026-11-02)
Phases 2–4 needed the **candidate section of `docs/api-doc.md`** from `261102-1509-candidate-api-db-seed` phase 4. **It is now written** (3 endpoints with auth, shapes and error tables), and `apps/web/src/lib/api-types.ts` mirrors it. The backend code is still uncommitted on `feat/candidate-api-db-seed`, so `blockedBy` stays until that plan is committed. That's a git-only dependency (see Branch below).
- Phase 2 still re-checks the doc first. FE shapes come only from `api-doc.md`, never from backend code (AGENTS.md rule 2).

## Branch
Commit the backend work on `feat/candidate-api-db-seed` first, then `git switch -c feat/candidate-interview-fe` from it. All FE work goes there.

## Decisions (locked with user, 2026-11-02)
| Area | Decision |
|---|---|
| Route | `/i/[token]`, which matches the seed plan's printed link `{WEB_BASE_URL}/i/{token}` |
| Previous-question nav | **Dropped.** The API returns only the current question's text. No "← Previous question" link. "Back to this question" right after submit stays (question + text held in memory) |
| Backend changes | None. FE consumes the candidate API as specified |
| Theme | Light only. The design has no dark theme, so the `.dark` token block is removed |
| Token format | Hex values copied from the design (exact match). Exposed as shadcn semantic vars + extra status/brand vars, mapped into Tailwind via `@theme inline` |
| Font | Inter 400/500/600/700 via `next/font/google`. Geist is removed |
| Draft | "Draft saved on this device" = `localStorage`, per candidate + question, cleared after a successful submit |
| Mocks | Footer labels the invitation email as **mocked** (AGENTS.md rule 5) |
| Error copy | Friendly candidate wording per documented status/detail, falling back to the raw `detail` (validation 2026-11-02) |
| Audio MIME | If `file.type` is empty or not audio/video, re-wrap the file with a type inferred from its extension before upload, which avoids false 415s. No backend change (validation 2026-11-02) |

## Phases
| # | Phase | Status | Depends |
|---|---|---|---|
| 1 | [Design tokens + global theme](phase-01-design-tokens-and-global-theme.md) | done | none |
| 2 | [Candidate API client + types](phase-02-candidate-api-client-and-types.md) | done | 1 (api-doc gate satisfied) |
| 3 | [Candidate interview page](phase-03-candidate-interview-page.md) | done | 2 |
| 4 | [Verification + docs](phase-04-verification-and-docs.md) | done | 3 |

## Acceptance criteria
- [x] `globals.css` holds the full token set from phase 1. No raw hex values in candidate components (tokens only)
- [x] `docs/design-guidelines.md` documents every token and where it is used
- [x] `/i/<seeded token>` shows the role, first name, saved count, progress and the current question, matching `Interview.dc.html`
- [x] Typed answer: submit → receipt "Typed answer received at HH:MM" → "Next question →" goes to the next question; reload resumes there
- [x] Audio upload (click or drag-drop) → receipt "Audio file received at HH:MM"; wrong type or > 25 MB is blocked client-side; a valid file with an empty/odd browser MIME still uploads (type inferred from extension); server errors (409/413/415/422) are shown inline in friendly wording
- [x] "Back to this question" reopens the just-submitted question; resubmitting replaces the answer
- [x] Bad/rotated token → "This link isn't valid" screen; finished candidate → completion screen; last answer → completion shown on the receipt with no back button
- [x] `/i/*` responses carry `Referrer-Policy: no-referrer` and `X-Robots-Tag: noindex`
- [x] The UI never shows a score, grade or job status (none are in the API; nothing is hard-coded)
- [x] `make lint && make test` green; `pnpm build` succeeds

## Out of scope
HR pages (sign-in, dashboard, review) · previous-question navigation · in-browser mic recording · consent/mic check · error-retry UX beyond an inline message (brief optional extra) · dark mode · FE unit-test framework.

## Open questions
None blocking. Note: the data-pack candidates already have 1–2 answers, so seeded links open at Q2/Q3. Q1 → Q6 end-to-end can be smoke-tested only on a candidate with fewer answers, or by answering forward.

## Validation Log

### Session 1 — 2026-11-02 (trigger: candidate api-doc ready)

#### Verification Results
- Claims checked: 20
- Verified: 20 | Failed: 0 | Unverified: 0
- Tier: Standard (Fact Checker + Contract Verifier)
- Evidence: `docs/api-doc.md` has all 3 candidate endpoints; `api-types.ts` mirrors it field by field; seed link `/i/{token}` (`apps/api/app/seed/runner.py:182`); `MAX_AUDIO_BYTES = 25 MB` (`apps/api/app/core/config.py:13`); `ui/{button,badge,textarea,input,alert}.tsx` exist and `tabs.tsx` doesn't; `next.config.ts` has rewrites and no headers; no `middleware.ts`/`proxy.ts`
- Contract drift (wording only, now fixed in phase 2): 201 = created **or replaced**; 422 also covers a missing field; exact `detail` strings now documented

#### Questions & answers
1. Candidate error copy → **friendly copy per error**, raw `detail` fallback
2. Audio file with empty/odd MIME → **infer type from extension** client-side
3. Branch → **commit backend, then `feat/candidate-interview-fe` off `feat/candidate-api-db-seed`**

#### Propagation
- `plan.md`: branch, blocker → resolved, decisions table, audio acceptance criterion
- `phase-02`: gate marked satisfied; contract section replaced by the verified contract; `withAudioMime` helper + MIME map added
- `phase-03`: `candidate-error-messages.ts` added; state machine error lines point to it
- `phase-04`: step 0 (commit + branch); MIME helper check; friendly-copy check

#### Whole-Plan Consistency Sweep
- Re-read `plan.md` + phases 1–4. Searched for `blocker`, `BLOCKED`, `branch: main`, `server detail`, `201 new`.
- Stale "submit errors show raw server detail" lines in phase 3 → updated. Phase 2 "stop with BLOCKED" kept as a re-check guard only.
- Unresolved contradictions: 0
