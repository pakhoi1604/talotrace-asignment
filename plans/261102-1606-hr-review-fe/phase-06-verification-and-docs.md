---
phase: 6
title: "Verification + docs"
status: completed
priority: P1
dependencies: [3, 4, 5]
---

# Phase 6: Verification + docs

## Overview
Prove the HR area works end to end in a browser, confirm no backend file changed, update FE docs, then commit, push and remove the worktree.

## Requirements
- Functional: browser smoke of all 5 routes + the auth edges.
- Non-functional: gates green; docs match what shipped; scope guard holds.

## Implementation Steps
1. **Scope guard**
   ```bash
   git diff --stat main -- apps/api            # must be empty
   git diff main -- docs/api-doc.md            # must be empty (HR sections untouched)
   git diff --stat main -- apps/web/src/components/interview   # only interview-header.tsx (BrandMark swap)
   # colors: tokens only (must be empty). Covers hex, rgb/rgba/hsl, arbitrary color classes, inline color styles
   grep -rnE '#[0-9a-fA-F]{3,8}\b|rgba?\(|hsla?\(|(bg|text|border|ring|shadow|from|to|fill|stroke)-\[[^]]*(#|rgb|hsl)|style=\{\{[^}]*(color|background|border)' \
     apps/web/src/components/hr apps/web/src/app/hr apps/web/src/components/brand-mark.tsx
   # spot-check: every artboard color still maps (re-run the phase-1 step 1a inspection; list any gap in the report)
   git diff main -- apps/web/src/app/globals.css   # must be empty (rule 9)
   ```
2. **Gates**: `make lint && make test`; `cd apps/web && pnpm build`.
3. **Browser smoke** (`make seed && make dev`, use `ck:agent-browser`; screenshots into the phase report):
   - `/hr/roles/1` with no cookie → sign-in with `next`; wrong password → message; right → back to `/hr/roles/1`
   - role switcher, stats, sort Name/Highest/Newest
   - review page: queued state; override with reason; force a failed job (`sqlite3 apps/api/data/app.db "update scoring_jobs set status='failed', last_error='test', attempts=3, suggested_score=null, suggested_reason=null where id=…"`) → "No score yet" + Retry → queued
   - audio answer plays; "Transcription not built" label visible
   - candidate resubmits via `/i/{token}` → "Submitted 2× · this one counts" + earlier submission
   - `/hr/jobs`, `/hr/jobs?status=needs_person`, retry from the jobs table
   - sign out → sign-in; browser back → redirected
   - with the worker running (if landed): queued → scored after pressing Refresh; an open override form survives the refresh
   - candidate page `/i/<token>` header still looks identical after the `BrandMark` swap
   - 360px width: sign-in, table scroll, review cards stack
4. **Docs**
   - `docs/design-guidelines.md`: add an "HR area" section: shell/header/nav recipe, stat card, candidate table, status chip map (status → Badge variant → label, incl. running → "Queued"), and the HR design color → token map from phase 1 (role-based, no hex in code), score figure, review card tones per panel state, override form, empty states. Tokens only; no new tokens.
   - `docs/architecture.md`: frontend section, HR routes; client-side fetching through the `/api` rewrite; `proxy.ts` cookie-presence redirect (permissions stay in the backend); 401 → sign-in; manual Refresh (no polling); "not built" (Read first, Load data pack button, transcription, highlight of scorer-directed text).
   - `README.md`: "HR area" lines: URL `http://localhost:3000/hr`, sign in with `HR_EMAIL`/`HR_PASSWORD` from `apps/api/.env` (**MOCK sign-in**). Don't duplicate what the HR API plan already added; read the README first.
   - Do **not** edit `docs/api-doc.md` endpoint sections.
5. **Plan bookkeeping**: mark phases done in this plan; `plan.md` status `completed`.
6. **Ship**: commit (conventional, e.g. `feat(web): HR sign-in, candidates, review and jobs pages`), push `feat/hr-review-fe`, remove the worktree (AGENTS.md rule 10).

## Success Criteria
- [ ] Scope guard: the `apps/api`, `api-doc.md`, color (hex/rgb/hsl/arbitrary/inline) and `globals.css` checks are empty; under `interview/`, only `interview-header.tsx` changed
- [ ] `make lint && make test` green; `pnpm build` green
- [ ] Browser smoke checklist done, screenshots in `plans/261102-1606-hr-review-fe/reports/`
- [ ] Docs updated and consistent with the shipped UI
- [ ] Branch pushed, worktree removed

## Risk Assessment
- Worker not landed yet → no `scored` data for accept/refresh checks. Use `sqlite3` to set one job to `scored` with a score + reason (dev DB only) and note the gap in the report.
- Rewrite + audio Range issue found in smoke → record it. A Next route handler proxy is a follow-up decision for the user, not a silent addition.
