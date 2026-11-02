# Cook report — LLM scoring worker (Gemini)

- **Plan**: `plans/261102-1549-llm-scoring-worker/` (4 phases, all completed)
- **Branch**: `feat/llm-scoring-worker` — commit `4216276`, pushed to origin
- **Worktree**: `/home/khoipham/Projects/bamboo/talotrace-llm-scoring` (removed after ship)
- **Mode**: `--auto` on existing plan path (code mode)

## Outcome

| Gate | Result |
|---|---|
| `make test` | **282 passed**, 10 live deselected |
| `make lint` | ruff check + format, biome, tsc — all clean |
| `alembic check` | clean (no schema change) |
| `pytest -m live` (no key) | fails fast with clear message (not skips) — verified |
| Seeded-pack drain (FakeScoringLLM, real SQLite DB) | scored 27, needs_person 7 (A019 pre-scan + A007 empty + 5 audio), superseded 1 (A022), **0 queued/running left**, 27 LLM calls |
| Worker missing key | exits 2 with stderr banner, no DB access — verified |

## What was built

- `app/scoring/`: `inputs` (ORM-free dataclasses), `injection_scan` (NFKC + Cf strip + regex pre-scan + hidden-char hit), `prompt` (rubric-only system, nonce-fenced user, forged-tag neutralisation), `model_output` (strict `ModelScore`, extra forbid), `llm_client` (Gemini + error taxonomy: Transient/Permanent/RateLimited/Refusal; no temperature; max_output_tokens; response_schema), `score_answer` (retry loop, heartbeat-abort, ScoringOutcome validated via `validate_job_result`).
- `app/worker/`: `job_queue` (claim/heartbeat/fenced write/429 refund/lease recovery — all short Core UPDATEs, no txn across LLM calls), `runner` (run_once + run_forever, catch-all per job, 5s DB backoff, worker-scoped call throttle), `__main__` (exit 2 on missing key, key-scrubbing formatter, two-stage signal handling).
- Tests: 8 new files (~140 cases): fake LLM, strict output validation, pre-scan positives/27 negatives/pack regression (only A019), prompt fencing, retry taxonomy, claim race via `_next_queued_id` hook, attempts fence, lease/poison-job recovery, supersede-mid-run abort, 429 refund, cross-job throttle, exit-2.
- Config/ops: `SCORER_*`/`WORKER_*` settings + `.env.example`; `make worker`; `make dev` runs api+web+worker; AGENTS.md command row; `httpx` direct dep.
- Docs: `api-doc.md` job-status + `needs_person_reason` reference; `architecture.md` worker section (state machine, reliability, injection defence "tested, not absolute", not-built); README key/worker/stuck-queued/bad-key/live notes.
- `test_scorer_live.py` (opt-in): A019 pre-scan, clean baseline, 5 paraphrased attacks (pre-scan or needs_person/score≤baseline), ≤1 model flag on clean answers, ±1 vs 2 HR references.

## Deviations from plan

1. `score_answer(..., secrets=())` — added keyword for error redaction (pinned interface had no way to know the key value). Runner passes `settings.GEMINI_API_KEY`.
2. httpx **and** httpx2 transport exceptions caught — SDK accepts the drop-in fork; guarded import, 8 lines.
3. Heartbeat moved **after** `wait_before_call` (reviewer L1) — tighter "no call after supersede".
4. `OperationalError` re-raised from `run_once` into `run_forever`'s 5s backoff instead of failing the job (reviewer L6).

## Review findings applied

- **M1 (fixed)**: min-call-interval throttle was per-job → dead code across jobs. Hoisted `last_call_at` onto `WorkerDeps`; added `test_min_call_interval_applies_across_jobs`.
- **L2 (wontfix)**: `validate_job_result` permits score on needs_person — pre-existing shared invariant from the HR plan; read-side gate `visible_suggestion` already covers it. Out of scope here.
- **L4/L5/nits**: judged cosmetic; scrub formatter correctly guards empty secret (`"".replace` would corrupt logs).

## Not verified (needs real key / live env)

- `pytest -m live` against real Gemini (~12 calls) — no `GEMINI_API_KEY` in this env; failure mode verified.
- Whether live API accepts Pydantic `response_schema` (plan open question) — `-m live` surfaces it; dict-schema fallback not implemented.
- Ctrl-C under `make dev` orphan check, `kill -9` mid-job recovery — verified by design/tests, not manually executed.
- Seeded drain used FakeScoringLLM — acceptance criterion with real Gemini pending.

## Unresolved questions

- User's free-tier RPM/RPD — `WORKER_MIN_CALL_INTERVAL_SECONDS=4` (≈15 RPM) is the safe default; tune if quota allows.
- Live-eval score drift at default temperature — assertions have ±1/`needs_person`-or-≤ tolerance per plan.
