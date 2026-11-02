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
5. The scoring worker (`python -m app.worker`, started by `make dev`) claims `queued` jobs, routes audio/blank/injection-suspect answers to `needs_person` without a model call, otherwise calls Gemini, validates the output, and writes the score through a fenced update. The candidate API never exposes scores.
6. HR overrides or accepts via `/api/hr/answers/{id}/{override,accept}` — appended to `score_decisions` after a fresh-state re-check inside the write transaction (supersede and suggestion-vanish races can't store a stale decision). `retry` conditionally re-queues only `failed` jobs (double click → 200 no-op).

## Scoring worker

Separate process (`python -m app.worker`, `make worker`; `make dev` runs it alongside api + web). `scoring_jobs` is the durable queue; there are no new endpoints.

### Job state machine

```
queued ──claim (attempts+1)──▶ running ──▶ scored        (score 1–4 + reason + model)
   ▲                             │  ├────▶ needs_person  (audio | blank | pre-scan | model flag | refusal)
   │                             │  └────▶ failed        (calls used up | permanent | unexpected | claims ≥ max)
   ├──── 429 (claim refunded) ───┤                          └──HR retry (attempts=0)──▶ queued
   └──── lease expired ──────────┘
any status ──candidate resubmits──▶ superseded (worker write discarded by the fence)
```

One `run_once` pass: recover stale jobs → claim → no-LLM routes → prompt → Gemini → validate → fenced write.

### Scorer reliability

- **Validation before storage**: the model's JSON must be a strict `{"score": int 1–4, "reason": 1–2000 chars, "instruction_attempt": bool}` with no extra keys — invalid output is a transient retry, never a stored score. `ScoringOutcome` re-runs `validate_job_result`, so an invalid result can't be constructed.
- **Error taxonomy**: transient (timeout, network, 5xx, `MAX_TOKENS`, invalid output) retries in-run with 2s/4s backoff through the call throttle; permanent (400/401/403/404, missing key) fails the job at once with a clear `last_error` — a bad key fails jobs one by one, HR retries each (user decision); `RateLimited` (429) requeues with the claim refunded and pauses the worker by `retryDelay` (cap 300s); a refusal finish/block reason → `needs_person`; any other exception fails that job and the loop keeps going — the worker never dies on one job.
- **`attempts` = claims**, and the claim number is the **fence token**: every heartbeat/result write is `UPDATE … WHERE id AND status='running' AND attempts=claim_no`, so a stale worker can't overwrite a newer claim and a superseded job discards the late result.
- **Lease recovery**: `running` with `updated_at` older than 120s is requeued (or `failed` at ≥3 claims — "worker stopped mid-job"), so a crash or a poison job can't strand work. Each LLM call heartbeats first; the worst gap (~38s) is well under the lease.
- **No transaction spans an LLM call**: the read transaction commits before `score_answer`; every queue write is its own short Core UPDATE + commit (ORM events are bypassed — safe because `ScoringOutcome` already ran the result invariants and every outcome writes all score columns).
- **Signals**: first SIGINT/SIGTERM finishes the in-flight call, writes, exits; a second exits at once (the lease recovers the job). Ctrl-C under `make dev` leaves no orphan.

### Prompt injection defence

An answer that tries to instruct the scorer must not be able to buy a score. The layers:

1. **Cf strip** (`clean_text`: NFKC + drop format chars) — zero-width/bidi/tag tricks are removed before anything reads the text, and it's the same text the model and HR see.
2. **Deterministic pre-scan** — regexes that name the scorer, the rules or an explicit top score, plus any tag/bidi char. A match → `needs_person` with a neutral reason + quoted snippet, **no LLM call, no suggestion** (user decision: a human reads it, the attack can't win a score).
3. **Prompt fencing** — the answer goes in `<answer-{nonce}>` tags as untrusted data in `user`; the rubric and rules live only in the system instruction; forged fence tags in the text are neutralised.
4. **Strict output schema** + a narrowed `instruction_attempt` flag (only "asks for a score" or "change the rules" — greetings are not instructions). A flag → `needs_person`, no score.
5. **HR has the final say** — `needs_person` carries no suggestion to accept; only an override with a reason counts.

The false-positive trade-off is deliberate: an honest answer caught by the pre-scan costs one human read with a neutral reason — never a wrong score. The suite holds ~27 realistic negative sentences plus a data-pack regression (only A019 is flagged), and `pytest -m live` evals paraphrased attacks against the real model. **This defence is tested against known attacks — it is not a guarantee.** Paraphrases and non-English attacks can get past the pre-scan; the fence, flag and HR override are the backstop.

### What the worker is not

- **Missing `GEMINI_API_KEY`** → exits code 2 at startup with a loud stderr banner; jobs stay `queued`; api + web keep running.
- **A wrong key or model name** → each job `failed` with a clear `last_error`. Fix `.env`, restart the worker, retry in HR.
- **Dead under `make dev`** → not restarted (no supervisor loop); the banner makes it visible.

## Frontend

Next.js App Router in `apps/web`. The candidate interview page `/i/[token]` is a
client component that calls `/api/candidate/*` same-origin (the `next.config.ts`
rewrite proxies to FastAPI); the token lives in the URL path and the
`Authorization` header only, and `/i/*` responses carry `Referrer-Policy:
no-referrer` + `X-Robots-Tag: noindex`. All design tokens (colors, radii,
shadows, type scale, containers) live in `globals.css` — see
`docs/design-guidelines.md`. Typed drafts persist in `localStorage` per
candidate+question until submit.

The HR area lives under `/hr`: `/hr/sign-in` (MOCK), `/hr` (redirects to the
first role), `/hr/roles/[roleId]`, `/hr/candidates/[candidateId]` and
`/hr/jobs?status=`. All HR pages are client components that call `/api/hr/*`
same-origin through the rewrite, sending the httpOnly `hr_session` cookie;
`cache: "no-store"` on every GET. `src/proxy.ts` (Next 16 proxy, the former
middleware) redirects `/hr/*` to sign-in when the cookie is absent — presence
only; permissions stay in the backend, and any 401 from an HR call redirects
to `/hr/sign-in?next=` (`next` is validated to `/hr/*` only). Refresh is
manual (a Refresh button, no timers/polling). The brand mark is shared as
`src/components/brand-mark.tsx`; the candidate header is unchanged. HR routes
are `noindex`. Not built on the frontend: "Read first" ordering, a "Load data
pack" button, audio transcription (labelled "Transcription not built"), and
the scorer-instruction highlight from the mockup (the API returns no span).

## What we chose not to build

From the brief's "Optional extras", excluded on purpose:

- HR-score agreement report
- Audio transcription/scoring
- "Needs a person" list view (the `needs_person` **job status** is still required)
- Ordered candidate list / "Read first" ordering
- Consent screen / mic check
- Candidate error + retry UX
- Previous-question navigation (the API only returns the current question)
- In-browser mic recording
- Deployed demo
- Rate limiting on HR sign-in, CSRF tokens, multi-user HR/roles, session sweeping, a "Load data pack" button (use `make seed`), and a tighter candidate upload content-type allow-list (the HR audio route already ignores the stored type)
- Audio transcription (audio answers go to HR as `needs_person`, labelled)
- Bulk job retry; a persisted retry schedule
- Multi-worker tuning (the claim/fence protocol is already safe for >1 worker)
- Prompt version tracking; a second LLM call for injection detection
- Non-English / confusable-letter pre-scan patterns

## API endpoints

See `docs/api-doc.md` (single source of truth).
