# TaloTrace — HR interview-scoring take-home

Candidates answer screening questions via a token link; the system scores answers with an LLM and suggests a grade; HR reviews and decides. The system suggests, HR decides.

## Prerequisites

- [uv](https://docs.astral.sh/uv/) (Python package manager; installs Python 3.12 automatically)
- Node.js ≥ 20
- [pnpm](https://pnpm.io/) ≥ 9
- GNU make (Windows: use WSL)

## Setup

```sh
make setup
```

Then put your `GEMINI_API_KEY` (from [Google AI Studio](https://aistudio.google.com/)) into `apps/api/.env`.

## Run

```sh
make dev    # api on :8000, web on :3000 — Ctrl-C stops both
```

Open http://localhost:3000 — the home page shows live API + DB health.

## Test & lint

```sh
make lint
make test
```

## Database

SQLite at `apps/api/data/app.db` (gitignored). Never hand-write migrations — edit the
SQLAlchemy models, then `make migration m="what changed"`, review the generated
file, and `make migrate`.

## Mocks

Anything not wired to a real service is labelled "mock" in the UI and docs
(e.g. HR sign-in). Scoring calls the real LLM — no canned results.

## Docs

- `docs/api-doc.md` — API contract, **single source of truth**
- `docs/architecture.md` — architecture notes
- `AGENTS.md` — agent/dev rules
- `business-systems-pack/` — take-home data (read-only)
