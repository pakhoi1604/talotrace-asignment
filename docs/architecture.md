# Architecture

## Data model

```
roles 1─* candidates 1─* answers *─1 questions
                              1─1 scoring_jobs (+ result columns)
                              1─* score_decisions   (newest sequence counts)
hr_sessions                   (standalone; email is the HR identity)
```

- `roles` — the five open roles from the data pack (`title` unique).
- `questions` — the six interview questions (`Q1`–`Q6`), ordered by `position`, each with a `rubric` JSON (`{"1".."4"}`).
- `candidates` — one row per pack candidate: identity + `role_id`, plus `access_token_hash` (sha256 of the link token; the raw token is never stored) and `token_issued_at`. `make seed` rotates these on every run.
- `answers` — every submitted version is kept. `kind` is `text` or `audio` (CHECK, with matching payload columns). A **partial unique index** on `(candidate_id, question_id) WHERE superseded_at IS NULL` guarantees at most one *current* answer per pair — that's what makes double-submit races safe.
- `scoring_jobs` — one job per answer (`answer_id` unique). `status` is a CHECK'd string: `queued`, `running`, `scored`, `failed`, `needs_person`, `superseded`. Result columns: `suggested_score`, `suggested_reason`, `needs_person_reason`, `model`, `finished_at` (all nullable).
- `score_decisions` — **append-only** HR decisions (`override` \| `accept`). `UNIQUE(answer_id, sequence)` makes concurrent writers collide instead of duplicating; CHECKs enforce `kind`, `score 1–4`, and that overrides carry a reason. The newest sequence counts; edits append a row so earlier HR reasons are kept — including on superseded answers, where they stay visible under `earlier_submissions`.
- `hr_sessions` — MOCK sign-in sessions: `token_hash` (sha256 of the raw cookie token), the canonical `.env` `email`, a `credential_fingerprint` (HMAC of the account — changing `HR_EMAIL`/`HR_PASSWORD` in `.env` revokes every session), `expires_at` (checked in SQL, not Python, because SQLite returns naive datetimes).

### Job-result invariants live in the ORM, not the DB

The result-column rules (score 1–4; `scored` has score + reason; `queued`/`running`/`failed` have no score; `needs_person` has a reason) are enforced by `ScoringJob.check_result_invariants()` on `before_flush` plus a `@validates` on `suggested_score` — **not** by CHECK constraints. Alembic autogenerate can't add CHECKs to an existing table and hand-written migrations are banned (user decision); tests build the schema with `create_all`, so model CHECKs would also diverge test/prod. One module-level `validate_job_result` holds the rules and is reused by the worker contract.

The gap is closed on the read side too: `hr_review.visible_suggestion` exposes `suggested_score`/`suggested_reason` only for `scored`/`needs_person` jobs, so a bad row (raw SQL, bulk update, buggy worker) can never surface a failed job as a score. The one bulk-update site (`retry_job`) clears every score column in the same statement.

## HR auth (MOCK)

- Sign-in is a **mock**: one account from `HR_EMAIL`/`HR_PASSWORD` in `apps/api/.env`, labelled MOCK in UI and docs. `.env.example` ships `HR_PASSWORD=hr-demo-password`, live right after `make setup` — an accepted risk for evaluators; change it for any shared setup (changing the credentials signs everyone out via the fingerprint).
- The session is a random token (sha256 stored) sent as an httpOnly `hr_session` cookie (`SameSite=Lax`, `Path=/`, `Secure` only when `HR_COOKIE_SECURE`). Sign-out deletes the row; `DELETE` is idempotent (always 204, empty body — the frontend must not parse JSON).
- HR routes read **only** the cookie and never `Authorization`, so a candidate Bearer token can't cross over. Every failure is the same 401. There is exactly one guarded-route set, pinned by a route-table test.
- **CSRF**: HR `POST`s require `Content-Type: application/json` (415 otherwise). The API mounts no CORS middleware, so a cross-origin JSON request fails preflight and an HTML form can't send JSON — SameSite is not relied on alone.
- Expired session rows aren't swept (tiny table); no rate limiting on sign-in (mock).

## Final score

Newest `score_decisions` row → `"hr"`; else the suggestion of a `scored` job → `"suggested"`; else `null`. `needs_person` has no final score until HR overrides (accept is rejected there), `failed` never has one. `avg_suggested` counts `scored` jobs only. A candidate resubmission starts a fresh final score.

## Answer lifecycle: submission → job → score

1. A candidate `PUT`s text or audio to `/api/candidate/answers/{question_id}` (Bearer token auth). Audio streams to `UPLOAD_DIR` under a size cap and is hashed while streaming; the file is named after the answer id, so a committed file implies a committed answer (a crash between rename and commit can leave an orphan — accepted, not built).
2. `record_answer` writes the answer and a `queued` scoring job in **one transaction** — an answer always has exactly one job.
3. Latest wins: resubmitting different content sets `superseded_at` on the old answer and `superseded` on its job — whatever status that job had. **The worker must re-check that its job is still `running` and the answer is still current before writing a score.**
4. Identical content is a no-op replay (`200`, same receipt, nothing written), which also makes retries and double-clicks safe. If two different submissions race, the partial unique index forces the loser into `409 please retry` — never two current answers.
5. The scoring worker (later plan) picks up `queued` jobs, calls Gemini, writes the score the candidate API never exposes.
6. HR overrides or accepts via `/api/hr/answers/{id}/{override,accept}` — appended to `score_decisions` after a fresh-state re-check inside the write transaction (supersede and suggestion-vanish races can't store a stale decision). `retry` conditionally re-queues only `failed` jobs (double click → 200 no-op).

## Worker contract (for the scoring-worker plan)

- Claim with `UPDATE … WHERE status='queued'`; write results only `WHERE status='running'` and only after calling `validate_job_result`.
- Write **every** score column on each outcome; on failure clear them all in the same statement.
- Re-check the answer is still current before writing a score (step 3 above).

## What we chose not to build

From the brief's "Optional extras", excluded on purpose:

- HR-score agreement report
- Audio transcription/scoring
- "Needs a person" list view (the `needs_person` **job status** is still required)
- Ordered candidate list / "Read first" ordering
- Consent screen / mic check
- Candidate error + retry UX
- Deployed demo
- Rate limiting on HR sign-in, CSRF tokens, multi-user HR/roles, session sweeping, a "Load data pack" button (use `make seed`), and a tighter candidate upload content-type allow-list (the HR audio route already ignores the stored type)

## API endpoints

See `docs/api-doc.md` (single source of truth).
