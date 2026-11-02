---
phase: 1
title: "Repo root, agent rules, docs"
status: completed
priority: P1
dependencies: []
---

# Phase 1: Repo root, agent rules, docs

## Overview
Initialise git and create the root files that every later phase relies on: ignore rules, agent rules, the API contract doc, and a README stub.

## Requirements
- Functional: git repo, `.gitignore`, `AGENTS.md`, `CLAUDE.md` → `@AGENTS.md`, `docs/api-doc.md`, `docs/architecture.md`, `README.md`
- Non-functional: no secrets, no build output or dependency dirs tracked (the brief requires this)

## Related Code Files
- Create: `.gitignore`, `AGENTS.md`, `CLAUDE.md`, `README.md`, `docs/api-doc.md`, `docs/architecture.md`
- Do not touch: `business-systems-pack/`, `V2_*.pdf`, `.claude/`, `.agents/`, `.devin/`

## Implementation Steps
1. `git init -b main` (do not commit; the user commits).
2. `.gitignore`: `node_modules/`, `.next/`, `out/`, `.venv/`, `__pycache__/`, `.ruff_cache/`, `.pytest_cache/`, `*.db`, `*.db-wal`, `*.db-shm`, `apps/api/data/`, `apps/api/uploads/`, `.env`, `.env.*` with `!.env.example`.
3. `CLAUDE.md` (root), exactly:
   ```md
   @AGENTS.md
   ```
4. `AGENTS.md` sections (keep under ~120 lines):
   - **Project**: one paragraph. HR interview-scoring app. System suggests, HR decides. Link to the brief and `business-systems-pack/`.
   - **Layout**: `apps/api` (FastAPI), `apps/web` (Next.js), `docs/`.
   - **Commands**: `make setup|dev|lint|test`, plus per-app commands (`uv run ...`, `pnpm ...`).
   - **Rules** (hard):
     1. **Migrations**: never create or hand-write a migration file. Change SQLAlchemy models, then run `cd apps/api && uv run alembic revision --autogenerate -m "<what changed>"`. Review the generated file, then run `uv run alembic upgrade head`. Run `uv run alembic check` before you finish.
     2. **API contract**: `docs/api-doc.md` is the single source of truth. Any change to a backend endpoint (path, method, auth, request, response, error) updates `docs/api-doc.md` in the same change. The frontend learns endpoints and shapes only from `docs/api-doc.md`, not by reading backend code. FE types in `apps/web/src/lib/api-types.ts` mirror it.
     3. **Permissions live in the backend.** Never rely on hiding data in the UI. Candidate endpoints must never return grades, other candidates, or HR data.
     4. **Scorer must call the real LLM** (Gemini). No cached or fixed results in the app. Tests use a fake client injected via dependency.
     5. **Label every mock** in the UI and docs (sign-in, email, transcription).
     6. **Scope**: brief "Optional extras" are out of scope unless the user asks.
     7. **Gates before done**: `make lint && make test` green.
   - **Conventions**: Python snake_case modules, TS kebab-case files, shadcn components added only on demand via `pnpm dlx shadcn@latest add <name>`.
5. `docs/api-doc.md` template:
   - Header: base URL (`/api` via Next.js rewrite. Direct: `http://localhost:8000/api`), auth model (`candidate token` | `hr session (mocked)`), error shape `{ "detail": string }`, and the change rule.
   - One entry per endpoint, in a fixed format: `### GET /api/health`, then **Auth**, **Request**, **Response 200** (JSON example + field table), **Errors**.
   - Seed with only `GET /api/health` → `{ "status": "ok", "db": "ok" }`.
6. `docs/architecture.md`: headings only (Data model · API endpoints → link api-doc.md · Answer lifecycle: submission → job → score · What we chose not to build, pre-filled with the Optional-extras list). The brief requires this one-page note. Content is filled in by later plans.
7. `README.md` stub: prerequisites (uv, Node ≥20, pnpm, make), `make setup`, `make dev`, `make test`, env setup (`GEMINI_API_KEY`), links to `docs/`. Phase 4 finalises it.

## Success Criteria
- [x] `git status` shows no `.env`, `node_modules`, `.venv`, or `*.db` files
- [x] `CLAUDE.md` contains only `@AGENTS.md`
- [x] AGENTS.md rules 1 and 2 are written as shown above

## Risk Assessment
- `.claude/rules/CLAUDE.md` already exists (ClaudeKit). Root `CLAUDE.md` is separate, so they don't conflict.
- Whether to commit `.claude/`, `.agents/`, `.devin/` is the user's call. Leave them untracked-neutral (don't add them to .gitignore unasked).
