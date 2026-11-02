# LLM scoring worker: Gemini scorer + durable job queue

## What

Executed `plans/261102-1549-llm-scoring-worker/` test-first in worktree `feat/llm-scoring-worker` (commit `4216276`, pushed). ~140 failing tests across 7 files went in before a line of implementation; `apps/api/app/scoring/` (inputs, injection_scan, prompt, model_output, llm_client, score_answer) and `apps/api/app/worker/` (job_queue, runner, `__main__`) turned them green.

- **Queue**: `scoring_jobs` is the durable queue; `attempts` doubles as the claim fence token. Heartbeat + all writes are fenced on `(id, status='running', attempts=claim_no)` — a zombie worker that lost its lease can't clobber a reclaimed job. 120s heartbeat lease recovers crashed runs.
- **429**: requeues with the claim refunded so rate-limit retries don't burn attempt budget.
- **Prompt injection**: pre-scan (NFKC + `Cf` strip + regexes) routes hostile answers straight to `needs_person` with zero LLM calls.
- **Output safety**: strict `ModelScore` pydantic validation before any write; error text redacted to ≤500 chars (scrubs secrets).
- End-to-end drain on the real seeded pack with `FakeScoringLLM`: 27 scored, 7 needs_person (A019 injection + A007 empty + 5 audio), 1 superseded (A022), zero stuck queued/running.

## Key decisions

- `secrets` kwarg added to `score_answer` for error redaction — additive deviation from the pinned interface, accepted because leaking an API key in a job error is worse than a signature drift.
- httpx/httpx2 dual exception handling kept — the Gemini SDK accepts either fork; pinning one would break the other env.
- `OperationalError` escapes `run_once` into the 5s backoff instead of being swallowed per-claim — DB blips shouldn't spin the loop.

## Bugs found & fixed (code-review subagent)

- **Medium**: min-call-interval throttle state reset per job — dead code across jobs. Hoisted `last_call_at` onto `WorkerDeps` + added a cross-job throttle test.
- Heartbeat now fires *after* the backoff wait, so a sleeping worker doesn't look dead mid-backoff.

## Verification

282 tests pass; 10 `live`-marked deselected (opt-in `pytest -m live`, needs `GEMINI_API_KEY` — verified it fails fast, doesn't silently skip). `make lint` + `alembic check` green.

## Open items

- Live eval against real Gemini is unverified — no key in this env. Whether the live API accepts the Pydantic `response_schema` is exactly what `-m live` will surface.
- Signals and `make dev` orchestration are verified by design, not execution.
