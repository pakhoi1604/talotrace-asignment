---
title: "LLM scoring worker (Gemini)"
description: "Background worker process that claims queued scoring jobs, scores typed answers 1–4 against the question rubric with real Gemini, validates the model output before storing, routes audio, blank and prompt-injection answers to needs_person, and fails visibly with retry."
status: completed
priority: P1
branch: feat/llm-scoring-worker
tags: [backend, llm, worker, reliability, tdd]
blockedBy: [261102-1531-hr-review-api]
blocks: []
created: 2026-11-02
---

# LLM scoring worker (Gemini)

Source brief: `V2_Full_Stack_Engineer_Take_Home_Brief.pdf` §4 "Scoring as a background job" + "What must be true". Reliability is weighted most by the graders.

## Goal
Every `queued` job ends in exactly one clear state:
- `scored`: score 1–4 + reason
- `needs_person`: reason
- `failed`: `last_error`, HR can retry
- `superseded`

The scorer calls real Gemini (AGENTS.md rule 4). Output is validated before storage. An answer that tries to instruct the scorer cannot change its score: it goes to `needs_person` with no suggestion. This is tested, not absolute (see phase 4). **Backend only, no new endpoints.**

## Decisions (locked with user, 2026-11-02; red-team updates marked RT)
| Area | Decision |
|---|---|
| Worker topology | **Separate process** `python -m app.worker`. New `make worker`, and `make dev` starts api + web + worker. `scoring_jobs` is the durable queue |
| Prompt injection | Deterministic pre-scan first. **On a match → `needs_person`, no LLM call, no suggested score.** Defence in depth for paraphrases the regex misses: the model gets Cf-stripped text fenced with a per-call nonce, the rubric goes only in the system instruction, output follows a strict JSON schema, and the model sets an `instruction_attempt` flag (narrowed to score requests and rule changes; greetings are not instructions). A model flag → `needs_person`, no score. The stored reason is neutral wording + quoted candidate text (RT) |
| No-LLM routes | audio → `needs_person` ("audio answer, not transcribed (transcription not built)"); blank/whitespace text → `needs_person` ("empty answer") (RT, user 2026-11-02); pre-scan hit → `needs_person` |
| Model call (RT) | Default temperature (Gemini 3 guidance). `max_output_tokens` capped. `response_schema` = `ModelScore`. Any finish reason other than `STOP`, or any `block_reason` → `needs_person` ("model declined to score: <REASON>"), except `MAX_TOKENS`, which counts as one transient retry |
| Attempts (RT) | `scoring_jobs.attempts` = **number of claims** (runs). Each run makes up to `SCORER_MAX_CALLS`=3 LLM calls (local counter). After `WORKER_MAX_CLAIMS`=3 claims a job is `failed` ("worker stopped mid-job"), so poison jobs can't loop |
| Transient vs permanent | Transient (retry within the run, backoff 2s/4s through the call throttle): timeout, network, 5xx, `UnknownApiResponseError`, generic `APIError`, invalid/out-of-schema JSON. **Permanent → that job `failed` at once (user kept this, 2026-11-02):** 400/401/403/404. A bad key or model fails jobs one by one with a clear `last_error`. HR retries each. README warns about it |
| Rate limit (RT) | 429 → `RateLimited(retry_after)` from the error's `retryDelay` (default 30s). Job goes back to `queued` with its claim refunded (`attempts - 1`). Worker pauses `retry_after` (cap 300s, logged). Never counts toward `failed` |
| Unexpected errors (RT) | Catch-all in `run_once`: any other exception → fenced `failed` with redacted `last_error`. `run_forever` logs (key-scrubbed) and keeps looping. DB errors → back off 5s and loop. The worker never dies on one job |
| Write fencing (RT) | Every heartbeat/write is `UPDATE … WHERE id=:id AND status='running' AND attempts=:my_claim`. rowcount 0 → superseded or re-claimed, so the result is discarded and logged as "no longer ours". A False heartbeat aborts the run (no more LLM calls). Values come from a validated `ScoringOutcome` that runs HR plan's `validate_job_result` |
| Crash recovery (RT) | `running` with `updated_at` older than `WORKER_LEASE_SECONDS`=120 → `queued` (or `failed` once claims ≥ max). Each LLM call heartbeats first, so a live run never goes > ~40s without one. Runs at startup and on every poll |
| Signals (RT) | First SIGINT/SIGTERM → finish the current LLM call, write, exit. Second signal → exit now (lease recovers the job). Ctrl-C under `make dev` sends SIGINT and then `kill 0` sends SIGTERM, so the worker exits at once with no orphan |
| Missing API key | Worker exits code 2 at startup with a loud stderr message. Jobs stay `queued`. API + web keep running. README: "jobs stuck in queued → check the worker output" |
| Clock (RT) | `now()` returns aware UTC `datetime` (`app.core.time.utcnow`), `monotonic()` returns a float for the throttle. Every bulk UPDATE sets `updated_at` explicitly |
| Live eval | Opt-in `pytest -m live`. **Fails** (not skips) without a key when selected. Covers A019 pre-scan, ~5 paraphrased attack variants vs the clean baseline, ≤ 1 clean answer model-flagged, and 2 HR-reference answers ±1 |

## Phases
| # | Phase | Status | Depends |
|---|---|---|---|
| 1 | [Write failing tests first](phase-01-write-failing-scorer-tests-first.md) | completed | none |
| 2 | [Scorer core: config, prompt, validation, pre-scan, Gemini client](phase-02-scorer-core.md) | completed | 1 |
| 3 | [Job queue + worker process](phase-03-job-queue-and-worker-process.md) | completed | 2 |
| 4 | [Live eval, docs, gates](phase-04-live-eval-docs-gates.md) | completed | 3 |

Test-first (AGENTS.md rule 8): phase 1 writes the suite red. Phases 2–3 turn it green **without weakening tests**.

## Job state machine
```
queued ──claim (attempts+1)──▶ running ──▶ scored        (score 1–4 + reason + model)
   ▲                             │  ├────▶ needs_person  (audio | blank | pre-scan | model flag | refusal)
   │                             │  └────▶ failed        (calls used up | permanent | unexpected | claims ≥ max)
   ├──── 429 (claim refunded) ───┤                          └──HR retry (attempts=0)──▶ queued
   └──── lease expired ──────────┘
any status ──candidate resubmits──▶ superseded (worker write discarded by the fence)
```

## Acceptance criteria
- [ ] `make seed && make dev` with real Gemini:
  - the 29 current typed answers reach `scored` or `needs_person`
  - A022 is `superseded` (A023 replaced it)
  - A019 → `needs_person` (pre-scan, zero LLM calls)
  - A007 → `needs_person` (empty answer)
  - 5 audio → `needs_person`
  - no `queued`/`running` left
- [ ] Model output is parsed and validated (strict int 1–4, non-blank reason ≤ 2000 chars, bool flag, no extra keys) before any write. Invalid output → retry → `failed`, never a stored score
- [ ] `failed` jobs carry `last_error` (no secrets, ≤ 500 chars) and null scores. HR retry → worker picks them up again
- [ ] An unexpected exception inside a job → that job `failed`. The worker keeps running
- [ ] A job that crashes the worker before any LLM call ends `failed` after `WORKER_MAX_CLAIMS` recoveries
- [ ] A job superseded while `running` stays `superseded`. No LLM call after the heartbeat sees it
- [ ] Two claimers can't take the same job (race forced via hook). A stale worker can't overwrite a newer claim (fence test)
- [ ] 429 → job back to `queued`, attempts unchanged, worker paused
- [ ] Pre-scan flags A019 and **no other** typed pack answer, and none of ≥ 20 realistic negative sentences
- [ ] Fake LLM in all default tests. `make test` is unaffected by `apps/api/.env`. `pytest -m live` passes against real Gemini
- [ ] Docs updated:
  - `docs/architecture.md`: worker, state machine, injection defence "tested, not absolute", not-built list
  - `docs/api-doc.md`: job status + `needs_person_reason` reference
  - README: `GEMINI_API_KEY`, worker, `make worker`, stuck-queued and bad-key notes
- [ ] `make lint && make test` green. `uv run alembic check` clean (no schema change)

## Out of scope
- HR frontend (status badges, retry button: separate FE plan)
- audio transcription
- HR-agreement report
- persisted retry schedule
- bulk retry
- multi-worker tuning
- prompt versioning column
- a second LLM call for injection detection
- confusable-letter / non-English pre-scan patterns
- a restart loop in `make dev`

## Cross-plan changes
- `261102-1531-hr-review-api`:
  - frontmatter `blocks: [261102-1549-llm-scoring-worker]`
  - phase 2 exposes `validate_job_result(...)` as a module function (applied)
  - its phase 1 factories `make_audio_answer` / `set_job_result` are reused here
  - accept is disallowed on `needs_person` there, which fits this plan (no suggestion, so HR overrides)
  - HR retry resets `attempts=0`, which matches the claim-count fence
- `261102-1529-design-tokens-candidate-interview-fe`: no overlap.

## Open questions
- Free-tier RPM/RPD for the user's key: check the AI Studio quota page. `WORKER_MIN_CALL_INTERVAL_SECONDS` is configurable, and 429 handling covers mistakes.
- Whether the live API accepts `additionalProperties: false` in `response_schema`: phase 2 falls back to a plain dict schema. Our validator is the gate either way.

## Red Team Review

### Session — 2026-11-02
**Findings:** 15 (15 accepted, 7 of them only in part; 0 rejected whole). 26 raw findings from 3 reviewers, merged.
**Severity breakdown:** 2 Critical, 6 High, 7 Medium
Reports: `reports/from-code-reviewer-to-planner-red-team-{security-adversary,failure-mode-analyst,assumption-destroyer}-plan-review-report.md`

| # | Finding | Severity | Disposition | Applied To |
|---|---|---|---|---|
| 1 | No exception boundary, so the worker dies and the job is stranded | Critical | Accept | plan, P1, P2, P3 |
| 2 | Poison jobs loop, because attempts only count LLM calls | Critical | Accept (attempts = claims) | plan, P1, P3 |
| 3 | 429/quota/config errors cascade to failed | High | Accept part: 429 requeue + pause. Config errors keep "fail each job" (user decision) | plan, P1, P2, P3, P4 |
| 4 | temperature 0 on Gemini 3; finish reasons partly handled; no token cap | High | Accept | plan, P1, P2 |
| 5 | Tests read the developer's `.env` (hang / network / skip-green live) | High | Accept | plan, P1, P3, P4 |
| 6 | Pre-scan false positives + accusatory reason | High | Accept | plan, P1, P2 |
| 7 | Unicode bypass; the model sees text HR doesn't | High | Accept part: Cf strip + same text to model + tag/bidi = hit. Rejected: confusables, Vietnamese patterns | P1, P2 |
| 8 | Model flag not independent; thin live eval | High | Accept part: ~5 attack variants + "tested, not absolute". Rejected: 2nd LLM call | plan, P4 |
| 9 | Rule 3 flags greetings; no cap on needs_person | Medium | Accept part: narrow rule 3 + ≤ 1 flag criterion. Rejected: advisory score (conflicts with user decision) | plan, P2, P4 |
| 10 | Status-only fence lets a stale worker overwrite a newer claim | Medium | Accept (fence on `attempts`) | plan, P1, P3 |
| 11 | Heartbeat result ignored | Medium | Accept | plan, P1, P2, P3 |
| 12 | Clock type mix-up; `onupdate` fires with the real clock | Medium | Accept | plan, P1, P3 |
| 13 | A007 empty; A022 always superseded | Medium | Accept (blank → needs_person, user decision) | plan, P1, P2 |
| 14 | Race tests can't force the race; cached reads; undefined input types; audio factory breaks the CHECK | Medium | Accept | P1, P2, P3 |
| 15 | 600s lease vs "requeued on start"; orphan worker on Ctrl-C | Medium | Accept part: 120s lease + second-signal exit. Rejected: restart loop | plan, P3 |

Also rejected:
- a 30s settle delay before scoring (scope)
- cutting the race test or the HR-reference sanity check (cheap, and they prove must-haves)

Verified true by reviewers:
- SDK timeout is in ms
- `ClientError`/`ServerError` have `.code`
- no SDK auto-retry
- `gemini-3.5-flash-lite` exists
- only A019 is flagged in the pack
- busy_timeout is already set in `session.py`

### Whole-Plan Consistency Sweep
- Files reread: plan.md, phase-01 … phase-04 (all rewritten from the accepted findings), plus HR plan phase-02/05 worker contract
- Decision deltas checked: 12. Changed: attempts = claims + fence token; `SCORER_MAX_CALLS`/`WORKER_MAX_CLAIMS` replace `SCORER_MAX_ATTEMPTS`; `heartbeat` replaces `bump_attempt`; lease 600→120s; default temperature; `RateLimited`; blank → needs_person; `AnswerInput`/`QuestionInput`; `now`/`monotonic` split; `main()` injection; acceptance 29 + A022; `make_text_answer` + HR factories
- Stale-term grep (`SCORER_MAX_ATTEMPTS`, `bump_attempt`, `max_attempts`, `lease_s`, `600`, `temperature 0`, `on_attempt`, `all 30`, `answer_snapshot`, `make_answer(`): matches only in the red-team log above (historical)
- Reconciled stale references: 1 (HR plan phase-02 worker write condition now names the attempts fence; HR phase-05 contract `WHERE status='running'` is a subset, still true)
- Unresolved contradictions: 0
