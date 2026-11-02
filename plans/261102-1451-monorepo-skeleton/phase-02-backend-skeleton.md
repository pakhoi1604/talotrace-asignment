---
phase: 2
title: "Backend skeleton (FastAPI + SQLite + Alembic)"
status: completed
priority: P1
dependencies: [1]
---

# Phase 2: Backend skeleton

## Overview
A uv-managed FastAPI app with settings, a SQLite engine (WAL), Alembic wired for autogenerate, one real endpoint (`/api/health`, checks the DB), ruff and pytest.

## Requirements
- Functional: `GET /api/health` returns `{"status":"ok","db":"ok"}` after running `SELECT 1` on the DB. Alembic upgrade creates the DB file.
- Non-functional: ruff clean, pytest green, no models yet (models come with the data-model plan)

## Architecture
```
app/main.py              create_app(): FastAPI, include routers under /api
app/core/config.py       pydantic-settings Settings: DATABASE_URL, GEMINI_API_KEY, GEMINI_MODEL, UPLOAD_DIR
app/db/base.py           class Base(DeclarativeBase), the metadata target for Alembic
app/db/session.py        engine + SessionLocal + get_db() dependency.
                         connect event: PRAGMA journal_mode=WAL; foreign_keys=ON; busy_timeout=5000
app/api/routes/health.py GET /health using Depends(get_db)
migrations/env.py        target_metadata = Base.metadata; url from Settings; render_as_batch=True
```
Sync SQLAlchemy keeps things simple. The future scoring worker is a separate process that shares the same SQLite file, and WAL + busy_timeout handle the concurrent writes.

## Related Code Files
- Create: `apps/api/pyproject.toml`, `uv.lock`, `.python-version` (3.12), `.env.example`, `alembic.ini`, `migrations/` (from `alembic init`), `app/**` as above, `tests/conftest.py`, `tests/test_health.py`

## Implementation Steps
1. `cd apps && uv init --app --name api --python 3.12 api && cd api` and delete the generated `main.py`/`hello.py`.
2. Deps: `uv add fastapi "uvicorn[standard]" sqlalchemy alembic pydantic-settings google-genai python-multipart`
   (`python-multipart` is needed for audio upload later. `google-genai` is the chosen LLM SDK. Settings-only for now, no client code.)
3. Dev deps: `uv add --dev ruff pytest httpx`
4. `pyproject.toml` ruff config: `line-length = 100`, `target-version = "py312"`, `[tool.ruff.lint] select = ["E","F","I","B","UP","SIM"]`. Add `[tool.pytest.ini_options] testpaths=["tests"]`.
5. Write `app/` modules per Architecture. `Settings` defaults: `DATABASE_URL="sqlite:///./data/app.db"`, `GEMINI_MODEL="gemini-3.5-flash-lite"`, `UPLOAD_DIR="./uploads"`, `GEMINI_API_KEY: str | None = None` (required later by the worker, optional for the skeleton). Ensure the `data/` dir exists before the engine is created.
6. `uv run alembic init migrations`. Edit `env.py`: import `Settings` and `Base`, set `sqlalchemy.url` from settings, `target_metadata=Base.metadata`, and `render_as_batch=True` in both offline and online `context.configure`. Leave `versions/` empty (no models yet, so no hand-written baseline).
7. `.env.example`: `DATABASE_URL=sqlite:///./data/app.db`, `GEMINI_API_KEY=`, `GEMINI_MODEL=gemini-3.5-flash-lite`, `UPLOAD_DIR=./uploads`.
8. Tests: `conftest.py` overrides `get_db` with an engine on a `tmp_path` SQLite file. `test_health.py` asserts 200 and the body.
9. Update `docs/api-doc.md` if the health shape changed from the Phase 1 seed.

## Success Criteria
- [x] `uv run ruff check . && uv run ruff format --check .` pass
- [x] `uv run pytest` passes
- [x] `uv run alembic upgrade head` creates `data/app.db`. `uv run alembic check` reports no changes
- [x] `uv run uvicorn app.main:app --reload` serves `GET /api/health` → `{"status":"ok","db":"ok"}`

## Risk Assessment
- SQLite ALTER limits: mitigated by `render_as_batch=True`.
- api + worker writes later: WAL + busy_timeout. If contention shows up in practice, revisit (not expected at this data size: 35 answers).
- `gemini-3.5-flash-lite` model id is unverified. It's configurable via env and gets verified in the scoring plan.
