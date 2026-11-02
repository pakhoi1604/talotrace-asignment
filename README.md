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

## Seed data

```sh
make seed
```

Loads `business-systems-pack/` (5 roles, 6 questions, 18 candidates, 35 answers
incl. 5 audio files) into SQLite and queues a scoring job per answer. Audio is
copied to `apps/api/uploads/` (gitignored).

**MOCK EMAIL:** instead of emailing candidates, the command prints each
candidate's access link and writes them to `apps/api/data/candidate-links.csv`
(gitignored). Links look like `http://localhost:3000/i/<token>` — send the token
as `Authorization: Bearer <token>`.

Re-running is idempotent for data (same counts, no duplicates) but **rotates
every token** — previous links stop working (`401`). Intended.

## Candidate interview

`make seed` prints each candidate's personal link (`/i/<token>`) and saves them
to `apps/api/data/candidate-links.csv`. Open one in a browser: the page shows
the current question, accepts a typed answer (draft autosaves on the device) or
an audio upload, and resumes where the candidate left off on reload. Invitation
emails are **mocked** — the links only exist via `make seed`.

## HR area

Open `http://localhost:3000/hr` and sign in with the **MOCK** account
(`HR_EMAIL`/`HR_PASSWORD` from `apps/api/.env`). Pages: a role's candidate
list with scoring-job counts, the per-answer review (suggested score + reason,
accept / override-with-reason / retry failed jobs), and `/hr/jobs` for every
scoring job including a "Needs a person" view. Data refresh is manual — press
the Refresh button; there is no polling.

## HR sign-in (MOCK)

The HR area uses a **mock sign-in**: a single account from `HR_EMAIL`/`HR_PASSWORD`
in `apps/api/.env` (defaults in `.env.example` are live after `make setup` — change
them for any shared setup). Sign in via `POST /api/hr/session`, which sets an
httpOnly `hr_session` cookie used by every `/api/hr/*` route. Changing the
credentials signs everyone out. Existing `apps/api/.env` files need the new
`HR_*` vars copied from `.env.example`.

## Mocks

Anything not wired to a real service is labelled "mock" in the UI and docs
(e.g. HR sign-in). Scoring calls the real LLM — no canned results.

## Docs

- `docs/api-doc.md` — API contract, **single source of truth**
- `docs/architecture.md` — architecture notes
- `AGENTS.md` — agent/dev rules
- `business-systems-pack/` — take-home data (read-only)
