# Monorepo skeleton: FastAPI api + Next.js web + SQLite

## What

Executed `plans/261102-1451-monorepo-skeleton/` end-to-end. Result: clean repo where `make setup && make dev` brings up the whole stack.

- `apps/api`: FastAPI on Python 3.12 via uv, SQLAlchemy 2.0 sync, Alembic (autogen-only, `render_as_batch`), SQLite file with WAL / `foreign_keys` / `busy_timeout` pragmas, pydantic-settings, ruff, pytest. `GET /api/health` → `{"status":"ok","db":"ok"}`, 503 `{"detail":"db unavailable"}` when the `SELECT 1` probe fails.
- `apps/web`: Next.js 16.4.3 App Router + TS, Tailwind v4 via `@tailwindcss/turbopack`, Biome 2.4 only (no ESLint), shadcn v4 `base-nova` preset with exactly the 10 required components, `next.config.ts` rewrites `/api/*` → `$API_URL/api/*`.
- Root `Makefile` (setup/dev/lint/format/test/migrate/migration), `AGENTS.md` hard rules (migration-autogen-only, api-doc.md is contract, permissions in backend, real-LLM scorer, labelled mocks, scope, lint+test gates), `docs/api-doc.md`, `docs/architecture.md` stubs, README.

## Key decisions

- `create-next-app` v16 has no `--eslint` flag; used native `--biome`.
- Kept scaffold `cacheComponents` + `partialPrefetching`. Route-segment `dynamic` exports now error in v16 → dynamic health fetch wrapped in `<Suspense>` instead.
- shadcn CLI v4 dropped `--base-color`; `-d` defaults produced the `base-nova` preset (pulls `@base-ui/react` underneath, not Radix — noted for anyone reaching for Radix docs later).
- `httpx2` replaces deprecated `httpx` for the starlette TestClient.
- Ruff `B008` per-file ignore in `health.py` — FastAPI `Depends()`-in-signature is idiomatic, flagging it is noise.
- Reviewer claim disproven: `alembic upgrade head` exits 0 with zero revisions (Alembic also auto-creates `versions/` on `revision`). Kept empty `versions/` + no baseline, per plan — no models exist yet.

## Bugs found & fixed

1. **`alembic upgrade head` failed on a clean clone.** `data/` dir creation lived in `session.py`, which Alembic's `env.py` never imports → engine couldn't open the DB file. Extracted `ensure_sqlite_dir` to `app/db/utils.py`, called from both `session.py` and `migrations/env.py`. Classic "works on my machine" — only fresh-clone verification caught it.
2. **`apps/web/.gitignore` scaffold `.env*` masked `.env.example`** → added `!.env.example`.
3. **Fresh-clone `tsc` failed**: `LayoutProps` types live in generated `.next/types` which doesn't exist until first dev/build → `"typecheck": "next typegen && tsc --noEmit"` self-heals.
4. Added `logger.exception` before the health 503 — silent 503s are useless at 2am.

## Verification

- `make setup` green on fresh state (`rm -rf .venv node_modules data`).
- `make lint` green: ruff check + format, biome check, tsc.
- `make test`: 1 passed (health test on tmp SQLite file).
- `make dev` e2e: api on :8000, proxy through `:3000/api/health`, page renders api/db ok badges, and correctly shows "API unreachable" with backend down.
- `make migration m="x"` with no model changes produced an empty revision (autogen wiring sanity check); deleted after.
- `git status` dry-run: no secrets or build artifacts staged.
- **Not committed** — plan says the user commits.

## Follow-ups

- Per plan order: (1) data model + seed loader, (2) candidate area, (3) HR area, (4) scoring worker — which will also add a `worker` process to `make dev`.
- Unresolved: `gemini-3.5-flash-lite` model id is unverified (env-configurable; verified in scoring plan). SQLite write contention between api + worker is theoretical — WAL + busy_timeout should cover ~35 answers; revisit only if it bites.
