# Architecture

One-page note. Details: `docs/architecture.md` · API contract (source of truth): `docs/api-doc.md`

## Stack

- `apps/api` — FastAPI + SQLAlchemy + Alembic, SQLite (file, WAL). Scoring is a separate worker process (`python -m app.worker`, started by `make dev`) that shares the DB as a durable job queue.
- `apps/web` — Next.js App Router; calls `/api/*` same-origin, proxied to FastAPI. Candidate interview under `/i/<token>`; HR area under `/hr`.

## Data model

```
roles 1─* candidates 1─* answers *─1 questions
                            1─1 scoring_jobs    (queue row + suggested score/reason/status)
                            1─* score_decisions (append-only HR accept/override; newest wins)
hr_sessions                                     (mock HR sign-in)
```

- `candidates.access_token_hash` — sha256 of the link token; the raw token is never stored.
- `answers` — every version kept; a partial unique index on `(candidate_id, question_id) WHERE superseded_at IS NULL` guarantees one *current* answer per pair, so resubmits supersede instead of duplicating.
- `scoring_jobs` — one per answer. `status`: `queued` → `running` → `scored` \| `needs_person` \| `failed` \| `superseded`.
- `score_decisions` — append-only, so HR history and reasons survive re-scoring and resubmits.

## API endpoints

| Route | Auth | Purpose |
|---|---|---|
| `GET /api/health` | — | liveness + DB check |
| `GET /api/candidate/interview` | Bearer link token | current question + progress (never returns scores) |
| `PUT /api/candidate/answers/{question_id}` | Bearer | submit text answer (idempotent) |
| `PUT /api/candidate/answers/{question_id}/audio` | Bearer | submit audio answer |
| `POST /api/hr/session` · `GET` · `DELETE` | httpOnly cookie | mock HR sign-in / check / out |
| `GET /api/hr/roles`, `GET /api/hr/roles/{id}/candidates` | cookie | roles, candidates per role with job counts |
| `GET /api/hr/candidates/{id}` | cookie | per-answer review: suggestion + reason + earlier submissions |
| `GET /api/hr/answers/{id}/audio` | cookie | stream the uploaded audio |
| `POST /api/hr/answers/{id}/{accept,override}` | cookie | HR decision (override requires reason) |
| `GET /api/hr/jobs?status=` · `POST /api/hr/jobs/{id}/retry` | cookie | all jobs incl. `needs_person`; re-queue `failed` |

Permissions live in the backend: candidate routes never return grades, other candidates, or HR data; HR routes read only the cookie, never the Bearer token.

## How an answer moves from submission to score

1. **Submit** — candidate PUTs text or audio. The API writes the answer and a `queued` scoring job in one transaction. Different content supersedes the old answer/job; identical content is a no-op replay, so retries and double-clicks are safe.
2. **Score** — the worker claims the job (the attempts counter is a fence token, so stale workers can't overwrite). Audio, blank, and injection-suspect answers skip the LLM → `needs_person`. Otherwise it calls Gemini with the rubric and a strict JSON schema → `scored` (score 1–4 + reason), or `failed` on permanent errors (HR can retry). A refusal or "asks for a score" flag also → `needs_person`.
3. **Decide** — HR sees the suggestion + reason and accepts or overrides (override requires a reason); each decision appends to `score_decisions`. Final score = newest HR decision, else the suggestion. **The system suggests, HR decides.**

## Chose not to build

From the brief's optional extras (all labelled MOCK / "not built" in the UI where visible):

- Audio transcription/scoring — audio goes to HR as `needs_person`
- HR–score agreement report; "needs a person" list view; ordered/"read first" candidate list
- Consent screen, mic check, in-browser recording; previous-question navigation
- Candidate error+retry UX; deployed demo
- Real email (links come from `make seed`); real HR accounts (mock sign-in)
- Rate limiting, CSRF tokens, multi-user HR, prompt-version tracking, multi-worker tuning
