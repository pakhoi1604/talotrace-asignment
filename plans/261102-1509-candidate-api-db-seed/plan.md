---
title: "Candidate API + DB schema + make seed"
description: "Candidate-side data model, token-link auth, answer submission API (text + audio) with latest-wins versioning and in-transaction job enqueue, and a `make seed` command that loads the data pack and prints access links."
status: pending
priority: P1
branch: main
tags: [backend, database, candidate, seed]
blockedBy: [261102-1451-monorepo-skeleton]
blocks: []
created: 2026-11-02
---

# Candidate API + DB + seed

Source brief: `V2_Full_Stack_Engineer_Take_Home_Brief.pdf` (Candidate area, "What must be true"). Data: `business-systems-pack/` (read-only).
Depends on skeleton (`apps/api` FastAPI + SQLAlchemy + Alembic + SQLite exists; plan status not yet ticked).

## Goal
Backend-only slice: a candidate opens a personal link, gets the current question, submits typed or audio answers, gets an instant receipt, and can reload and resume. `make seed` loads the data pack and prints one access link per candidate. **No frontend, no worker, no HR endpoints** in this plan.

## Decisions (locked with user, 2026-11-02)
| Area | Decision |
|---|---|
| Resubmission | **Latest wins.** Every version kept; newest = current, only one scored; older = `superseded_at` set, its job → `superseded`. Same content again = no-op (200, same receipt). Reason: data pack has C2052 re-recording Q3 (A022 → A023 "let me try that again") |
| Jobs | `scoring_jobs` table created now; answer + `queued` job inserted in **one transaction**. Worker = later plan |
| Tokens | `secrets.token_urlsafe(32)`, only sha256 stored. `make seed` **rotates all tokens every run**, prints links + writes gitignored CSV. Old links die |
| Demo data | None. Seed only the 18 pack candidates (1–2 answers each, 35 answers) |
| Order rule | Candidate may submit the current question (first unanswered by position) or replace an already-answered one. Others → 409 |
| Lock | Once all 6 questions have a current answer, interview is closed: replace → 409 |
| Candidate DTOs | Never contain score, rubric, job status, or other candidates. Enforced by separate Pydantic models + test |

## Phases
| # | Phase | Status | Depends |
|---|---|---|---|
| 1 | [Data model + migration](phase-01-data-model-and-migration.md) | pending | none |
| 2 | [Answer submission service](phase-02-answer-submission-service.md) | pending | 1 |
| 3 | [Candidate API endpoints + contract docs](phase-03-candidate-api-endpoints-and-docs.md) | pending | 2 |
| 4 | [Seed command + `make seed`](phase-04-seed-command-and-make-target.md) | pending | 2 |

Phases 3 and 4 are independent once 2 is done.

## Acceptance criteria
- [ ] `make setup && make seed` on a clean checkout: 5 roles, 6 questions, 18 candidates, 35 answers (34 current, A022 superseded), 35 jobs (34 `queued`, 1 `superseded`); 18 links printed and written to `apps/api/data/candidate-links.csv`
- [ ] Rerun `make seed`: same row counts, new tokens, old tokens → 401
- [ ] `GET /api/candidate/interview` with a seeded link returns role, progress and the current question; missing/bad token → 401
- [ ] Same `PUT` twice → one answer row, one job row, identical receipt (`200` on replay)
- [ ] Different content on answered question → new current answer, old one superseded + its job `superseded`
- [ ] Audio upload stored on disk under `UPLOAD_DIR`, answer `kind=audio`, job `queued`; bad type 415, oversize 413
- [ ] No candidate response contains `score`, `rubric`, `job`, or another candidate's data (recursive key test)
- [ ] `docs/api-doc.md`, `apps/web/src/lib/api-types.ts`, `docs/architecture.md` (data model), README + AGENTS.md (`make seed`) updated
- [ ] `make lint && make test` green; `uv run alembic check` clean

## Out of scope
Scoring worker + LLM · HR auth/endpoints · overrides · candidate frontend pages · transcription · token expiry · real email (links printed = labelled **MOCK email**) · demo candidates · `make reset-db`.

## Open questions
None blocking. Noted: pack `submitted_at` values are naive; stored as UTC.
