# AGENTS.md

## Project

HR interview-scoring take-home app. Candidates answer screening questions via a token link (typed or audio); the system scores each answer with an LLM and suggests a grade; a hiring manager reviews scores and reasons and makes the final call. **The system suggests, HR decides.** Source brief: `V2_Full_Stack_Engineer_Take_Home_Brief.pdf`. Data: `business-systems-pack/` (do not modify).

## Layout

- `apps/api` — FastAPI + SQLAlchemy + Alembic + SQLite (file on disk, WAL)
- `apps/web` — Next.js (App Router, TS, `src/`) + Tailwind v4 + Biome + shadcn
- `docs/` — `api-doc.md` (API contract, source of truth), `architecture.md`

## Commands

| Command | What it does |
|---|---|
| `make setup` | Install api + web deps, create `.env` files, run migrations |
| `make dev` | Run api (:8000) and web (:3000) together; Ctrl-C stops both |
| `make lint` | ruff check + format check (api), biome check + tsc (web) |
| `make format` | ruff format + fix (api), biome --write (web) |
| `make test` | pytest (api) |
| `make migrate` | `cd apps/api && uv run alembic upgrade head` |
| `make worker` | Run the scoring worker alone (`python -m app.worker`); `make dev` already starts it |
| `make seed` | Load `business-systems-pack/` into the DB, rotate candidate tokens, print + save access links (MOCK email) |
| `make migration m="..."` | Autogenerate a migration (the only way to create one) |

Per-app: `cd apps/api && uv run <cmd>` (pytest, ruff, alembic, uvicorn); `cd apps/web && pnpm <script>` (dev, lint, typecheck, build).

## Rules (hard)

1. **Migrations**: never create or hand-write a migration file. Change SQLAlchemy models, then run `cd apps/api && uv run alembic revision --autogenerate -m "<what changed>"`. Review the generated file, then run `uv run alembic upgrade head`. Run `uv run alembic check` before you finish.
2. **API contract**: `docs/api-doc.md` is the single source of truth. Any change to a backend endpoint (path, method, auth, request, response, error) updates `docs/api-doc.md` in the same change. The frontend learns endpoints and shapes only from `docs/api-doc.md`, not by reading backend code. FE types in `apps/web/src/lib/api-types.ts` mirror it.
3. **Permissions live in the backend.** Never rely on hiding data in the UI. Candidate endpoints must never return grades, other candidates, or HR data.
4. **Scorer must call the real LLM** (Gemini). No cached or fixed results in the app. Tests use a fake client injected via dependency.
5. **Label every mock** in the UI and docs (sign-in, email, transcription).
6. **Scope**: brief "Optional extras" are out of scope unless the user asks.
7. **Gates before done**: `make lint && make test` green.
8. **Backend is test-first**: when working on `apps/api`, write the failing test first, then implement. Verify the test fails before writing the code, and passes after.
9. **FE theme tokens**: do not change global theme/design tokens (CSS variables in `globals.css`, Tailwind theme config, shared color/spacing scales) unless the user explicitly asks.
10. **Cook workflow**: when cooking a task, create a new workspace (git worktree) checked out from `main` on a `feat/<task>` or `bug/<task>` branch. Do all work there, then commit and push, then remove the workspace.

## Conventions

- Python: snake_case modules. TypeScript: kebab-case files.
- shadcn components are added only on demand via `pnpm dlx shadcn@latest add <name>` (run in `apps/web`).
- Frontend calls `/api/*` same-origin; `next.config.ts` rewrites to FastAPI. Server components fetch `API_URL` directly.
