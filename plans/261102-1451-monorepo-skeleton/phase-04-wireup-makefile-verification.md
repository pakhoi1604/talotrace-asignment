---
phase: 4
title: "Wire-up, Makefile, verification"
status: completed
priority: P1
dependencies: [2, 3]
---

# Phase 4: Wire-up, Makefile, verification

## Overview
Root `Makefile` as the single entry point, a finalised README that runs on a clean machine, and a full verification pass.

## Requirements
- Functional: `make setup | dev | lint | test | migrate | migration m="..."`
- Non-functional: the README runs on a clean machine (a brief "must be true" item. Brief red flag: "The README does not run")

## Related Code Files
- Create: `Makefile`
- Modify: `README.md`, `AGENTS.md` (commands section), `docs/api-doc.md` (verify health entry)

## Implementation Steps
1. `Makefile` targets:
   ```make
   setup:      cd apps/api && uv sync && ([ -f .env ] || cp .env.example .env) && uv run alembic upgrade head
               cd apps/web && pnpm install && ([ -f .env.local ] || cp .env.example .env.local)
   dev:        run api (uvicorn --reload :8000) + web (pnpm dev :3000) together; Ctrl-C stops both (trap + wait)
   lint:       api: ruff check + ruff format --check ; web: biome check + tsc --noEmit
   format:     api: ruff format + ruff check --fix ; web: biome check --write
   test:       api: uv run pytest
   migrate:    cd apps/api && uv run alembic upgrade head
   migration:  cd apps/api && uv run alembic revision --autogenerate -m "$(m)"   # the only way to create migrations
   ```
   `dev` will get a `worker` process later (scoring plan). Leave no placeholder for it now.
2. README: prerequisites with versions, setup, `GEMINI_API_KEY` from Google AI Studio, run, test, project layout, links to `docs/architecture.md` and `docs/api-doc.md`. State the mocks policy ("mocked sign-in is labelled") briefly, ahead of the feature plans.
3. Verification on a fresh clone of the working tree: `rm -rf apps/api/.venv apps/web/node_modules apps/api/data`, then `make setup && make lint && make test`. Then `make dev` and load `http://localhost:3000`, which should show api/db ok.
4. `git status` check: nothing ignored is staged, no secrets.

## Success Criteria
- [x] All plan.md acceptance criteria are checked
- [x] Fresh setup works from the README alone, without extra steps
- [x] `make migration m="x"` with no model changes produces an empty revision. Delete it afterwards (sanity check that autogen is wired)

## Risk Assessment
- `make` + bash `trap` is not Windows-native. Acceptable: the reviewers run on mac/Linux per typical practice. Mention WSL in the README.
- `.env` copy uses `[ -f .env ] || cp ...` rather than `cp -n`, because `cp -n` behaves differently on GNU and BSD.
