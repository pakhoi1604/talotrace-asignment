---
title: "Candidate API + DB schema + make seed"
description: "Candidate-side data model, token-link auth, answer submission API (text + audio) with latest-wins versioning and in-transaction job enqueue, and a `make seed` command that loads the data pack and prints access links."
status: done
priority: P1
branch: feat/candidate-api-db-seed
tags: [backend, database, candidate, seed, tdd]
blockedBy: [261102-1451-monorepo-skeleton]
blocks: [261102-1529-design-tokens-candidate-interview-fe, 261102-1531-hr-review-api]
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
| 1 | [Write failing tests first](phase-01-write-failing-tests-first.md) | done | none |
| 2 | [Data model + migration](phase-02-data-model-and-migration.md) | done | 1 |
| 3 | [Answer submission service](phase-03-answer-submission-service.md) | done | 2 |
| 4 | [Candidate API endpoints + contract docs](phase-04-candidate-api-endpoints-and-docs.md) | done | 3 |
| 5 | [Seed command + `make seed`](phase-05-seed-command-and-make-target.md) | done | 3 |

**Test-first (user decision):** phase 1 writes the whole suite against the contracts in phases 2–5 and leaves it red. Each later phase is done when its suites go green **without weakening tests**. Phases 4 and 5 are independent once 3 is done.

## Acceptance criteria
- [x] `make setup && make seed` on a clean checkout: 5 roles, 6 questions, 18 candidates, 35 answers (34 current, A022 superseded), 35 jobs (34 `queued`, 1 `superseded`); 18 links printed and written to `apps/api/data/candidate-links.csv`
- [x] Rerun `make seed`: same row counts, new tokens, old tokens → 401
- [x] `GET /api/candidate/interview` with a seeded link returns role, progress and the current question; missing/bad token → 401
- [x] Same `PUT` twice → one answer row, one job row, identical receipt (`200` on replay)
- [x] Different content on answered question → new current answer, old one superseded + its job `superseded`
- [x] Audio upload stored on disk under `UPLOAD_DIR`, answer `kind=audio`, job `queued`; bad type 415, oversize 413
- [x] No candidate response contains `score`, `rubric`, `job`, or another candidate's data (recursive key test)
- [x] `docs/api-doc.md`: each candidate endpoint documents Auth, Request (field table + example), **every success code with a JSON example**, and an **Errors table listing every status code with its exact `detail`**; enforced by `test_api_doc_coverage.py`
- [x] All errors use `{ "detail": string }`, 422 included (custom validation handler)
- [x] `apps/web/src/lib/api-types.ts`, `docs/architecture.md` (data model), README + AGENTS.md (`make seed`) updated
- [x] `make lint && make test` green; `uv run alembic check` clean

## Out of scope
Scoring worker + LLM · HR auth/endpoints · overrides · candidate frontend pages · transcription · token expiry · real email (links printed = labelled **MOCK email**) · demo candidates · `make reset-db`.

## Open questions
None blocking. Noted: pack `submitted_at` values are naive; stored as UTC.
