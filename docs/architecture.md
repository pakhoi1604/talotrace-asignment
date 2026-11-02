# Architecture

## Data model

```
roles 1─* candidates 1─* answers *─1 questions
                              1─1 scoring_jobs
```

- `roles` — the five open roles from the data pack (`title` unique).
- `questions` — the six interview questions (`Q1`–`Q6`), ordered by `position`, each with a `rubric` JSON (`{"1".."4"}`).
- `candidates` — one row per pack candidate: identity + `role_id`, plus `access_token_hash` (sha256 of the link token; the raw token is never stored) and `token_issued_at`. `make seed` rotates these on every run.
- `answers` — every submitted version is kept. `kind` is `text` or `audio` (CHECK, with matching payload columns). A **partial unique index** on `(candidate_id, question_id) WHERE superseded_at IS NULL` guarantees at most one *current* answer per pair — that's what makes double-submit races safe.
- `scoring_jobs` — one job per answer (`answer_id` unique). `status` is a CHECK'd string: `queued`, `running`, `scored`, `failed`, `needs_person`, `superseded`.

## API endpoints

See `docs/api-doc.md` (single source of truth).

## Answer lifecycle: submission → job → score

1. A candidate `PUT`s text or audio to `/api/candidate/answers/{question_id}` (Bearer token auth). Audio streams to `UPLOAD_DIR` under a size cap and is hashed while streaming; the file is named after the answer id, so a committed file implies a committed answer (a crash between rename and commit can leave an orphan — accepted, not built).
2. `record_answer` writes the answer and a `queued` scoring job in **one transaction** — an answer always has exactly one job.
3. Latest wins: resubmitting different content sets `superseded_at` on the old answer and `superseded` on its job — whatever status that job had. **The worker must re-check that its job is still `running` and the answer is still current before writing a score.**
4. Identical content is a no-op replay (`200`, same receipt, nothing written), which also makes retries and double-clicks safe. If two different submissions race, the partial unique index forces the loser into `409 please retry` — never two current answers.
5. The scoring worker (later plan) picks up `queued` jobs, calls Gemini, writes the score the candidate API never exposes.

## Frontend

Next.js App Router in `apps/web`. The candidate interview page `/i/[token]` is a
client component that calls `/api/candidate/*` same-origin (the `next.config.ts`
rewrite proxies to FastAPI); the token lives in the URL path and the
`Authorization` header only, and `/i/*` responses carry `Referrer-Policy:
no-referrer` + `X-Robots-Tag: noindex`. All design tokens (colors, radii,
shadows, type scale, containers) live in `globals.css` — see
`docs/design-guidelines.md`. Typed drafts persist in `localStorage` per
candidate+question until submit.

## What we chose not to build

From the brief's "Optional extras", excluded on purpose:

- HR-score agreement report
- Audio transcription/scoring
- "Needs a person" list view (the `needs_person` **job status** is still required)
- Ordered candidate list
- Consent screen / mic check
- Candidate error + retry UX
- Previous-question navigation (the API only returns the current question)
- In-browser mic recording
- Deployed demo
