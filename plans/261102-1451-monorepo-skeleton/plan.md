---
title: "Monorepo skeleton: Next.js web + FastAPI api + SQLite"
description: "Scaffold repo layout, tooling, agent rules and API contract doc for the HR interview-scoring take-home. No features."
status: completed
priority: P1
branch: main
tags: [skeleton, frontend, backend, tooling]
blockedBy: []
blocks: []
created: 2026-11-02
---

# Monorepo skeleton

Source brief: `V2_Full_Stack_Engineer_Take_Home_Brief.pdf`. Data: `business-systems-pack/`.

## Goal
A clean repo where `make setup && make dev` starts api + web, both lint/test gates pass, and agents have clear rules. **Skeleton only**: no candidate/HR/scoring features (those are separate follow-up plans).

## Decisions (locked)
| Area | Choice |
|---|---|
| Layout | Single git repo, `apps/api` + `apps/web`, root `Makefile`. No turborepo/pnpm workspace (only 1 JS package) |
| FE | Next.js (App Router, TS, `src/`), Tailwind v4, Biome (no ESLint/Prettier), shadcn: required components only |
| BE | FastAPI, Python 3.12, uv, ruff (lint + format), pytest |
| DB | SQLite **file on disk** (`apps/api/data/app.db`, gitignored). No DB container. WAL + foreign keys on |
| ORM / migrations | SQLAlchemy 2.0 (sync) + Alembic **autogenerate only** (`render_as_batch` for SQLite) |
| LLM | Gemini via `google-genai`, model from env `GEMINI_MODEL` (default `gemini-3.5-flash-lite`) |
| API contract | `docs/api-doc.md`: single source of truth. FE reads it; BE updates it in the same change |
| FE→BE | Next.js rewrite `/api/*` → FastAPI `/api/*`, so browser calls are same-origin (no CORS, HR cookie works later) |
| Agent docs | `AGENTS.md` holds the rules; root `CLAUDE.md` = `@AGENTS.md` |

## Out of scope (brief "Optional extras", excluded on purpose)
HR-score agreement report · audio transcription/scoring · "needs a person" list view · ordered candidate list · consent screen / mic check · candidate error+retry UX · deployed demo.
Note: the `needs_person` **job status** is required (it's not optional). Only the dedicated list view is optional.

## Phases
| # | Phase | Status | Depends |
|---|---|---|---|
| 1 | [Repo root, agent rules, docs](phase-01-repo-root-agent-rules-docs.md) | completed | none |
| 2 | [Backend skeleton (FastAPI + SQLite + Alembic)](phase-02-backend-skeleton.md) | completed | 1 |
| 3 | [Frontend skeleton (Next.js + Tailwind + Biome + shadcn)](phase-03-frontend-skeleton.md) | completed | 1 |
| 4 | [Wire-up, Makefile, verification](phase-04-wireup-makefile-verification.md) | completed | 2, 3 |

Phases 2 and 3 are independent (disjoint dirs), so they can run in parallel.

## Target tree
```
.
├── AGENTS.md  CLAUDE.md  README.md  Makefile  .gitignore
├── docs/
│   ├── api-doc.md            # API contract, source of truth
│   └── architecture.md       # one-page note (brief deliverable), filled as features land
├── business-systems-pack/    # given data (unchanged)
└── apps/
    ├── api/   pyproject.toml uv.lock alembic.ini .env.example
    │          app/{main.py, core/config.py, db/{base.py,session.py}, api/routes/health.py}
    │          migrations/{env.py, script.py.mako, versions/}
    │          tests/test_health.py
    └── web/   package.json biome.json components.json next.config.ts .env.example
               src/app/{layout.tsx,page.tsx,globals.css}
               src/components/ui/*   src/lib/{utils.ts,api-client.ts}
```

## Acceptance criteria
- [x] `make setup` on a machine with uv, node ≥20, pnpm installs everything
- [x] `make dev` serves api :8000 and web :3000. Web home shows API + DB health fetched via `/api/health`
- [x] `make lint` passes: ruff check, ruff format --check, biome check, tsc --noEmit
- [x] `make test` passes: pytest health test using a temp SQLite file
- [x] `uv run alembic upgrade head` creates `data/app.db`. `alembic check` is clean
- [x] `AGENTS.md` contains the migration-autogen rule and the api-doc source-of-truth rule
- [x] No secrets committed. `.env` gitignored, `.env.example` present

## Follow-up plans (not this plan)
1. Data model + seed loader for `business-systems-pack` typed answers
2. Candidate area (token link, one question at a time, text/audio upload, idempotent submit, resume)
3. HR area (mock sign-in labelled, candidates by role, scores + reasons, override with reason, job statuses, retry)
4. Scoring worker (DB-backed job queue, Gemini call, output validation, prompt-injection resistance, fake client in tests)
