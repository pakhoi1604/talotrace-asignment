---
phase: 3
title: "Job queue + worker process"
status: completed
priority: P1
dependencies: [2]
---

# Phase 3: Job queue + worker process

## Overview
DB-backed queue operations (claim, heartbeat, fenced write, 429 requeue, stale recovery) and the `python -m app.worker` loop. Done = `test_job_queue.py` + `test_worker_runner.py` green, plus `make worker` scoring the seeded data pack.

## Requirements
- Functional:
  - one job scored once
  - supersede and newer claims win over a late result
  - crashed and poison jobs end in a clear state
  - HR retry is picked up
  - a 429 pauses the worker without failing jobs
  - the worker never dies on one job
- Non-functional: SQLite WAL (busy_timeout already set in `app/db/session.py:53`), short transactions (never hold one across the LLM call), structured log line per job, key-scrubbed logs.

## Architecture

### `app/worker/job_queue.py` (Core `update()`, each its own commit, **`updated_at=now` set explicitly in every statement**)
```python
def _next_queued_id(db) -> int | None:     # private hook, patched by the race test
    return db.scalar(select(ScoringJob.id).where(status == "queued")
                     .order_by(ScoringJob.created_at, ScoringJob.id).limit(1))

def claim_next_job(db, *, now) -> Claim | None:
    while (job_id := _next_queued_id(db)) is not None:
        res = db.execute(update(ScoringJob).where(id == job_id, status == "queued")
              .values(status="running", attempts=ScoringJob.attempts + 1, updated_at=now)); db.commit()
        if res.rowcount == 1:
            return Claim(job_id, db.scalar(select(ScoringJob.attempts).where(id == job_id)))
    return None

FENCE = lambda c: (ScoringJob.id == c.job_id, ScoringJob.status == "running", ScoringJob.attempts == c.claim_no)

def heartbeat(db, claim, *, now) -> bool:                 # UPDATE … SET updated_at=now WHERE FENCE
def write_outcome(db, claim, outcome, *, now) -> bool:
    UPDATE … SET status, suggested_score, suggested_reason, needs_person_reason, model,
                 last_error=outcome.error, finished_at=now, updated_at=now WHERE FENCE
def requeue_rate_limited(db, claim, *, now) -> bool:      # status='queued', attempts=attempts-1 WHERE FENCE

def recover_stale_jobs(db, *, now, lease: timedelta, max_claims) -> int:
    cutoff = now - lease
    UPDATE … SET status='failed', last_error='worker stopped mid-job', finished_at=now, updated_at=now
             WHERE status='running' AND updated_at < cutoff AND attempts >= max_claims
    UPDATE … SET status='queued', updated_at=now WHERE status='running' AND updated_at < cutoff
```
**Fence token = `attempts`** (claim count). A stale worker holds an older `claim_no` than any re-claim, and HR retry resets to 0 only from `failed`. Datetimes: `now` is always aware UTC from `app.core.time.utcnow`. SQLite stores it without an offset, so every value written and compared is UTC and the comparisons stay consistent.

Bulk UPDATEs skip ORM `before_flush`. That's safe because `ScoringOutcome` already ran `validate_job_result`, every outcome writes all score columns, and claim/heartbeat/recover/requeue never set score columns (they only move to `queued`/`running`/`failed`, which have null scores). This follows the HR plan's worker contract.

### `app/worker/runner.py`
```python
def run_once(deps) -> RunResult:
    with deps.session_factory() as db:
        recover_stale_jobs(db, now=deps.now(), lease=..., max_claims=...)
        claim = claim_next_job(db, now=deps.now())
        if claim is None: return IDLE
        try:
            job = db.get(ScoringJob, claim.job_id)
            answer_in, question_in = AnswerInput(...), QuestionInput(...)   # plain values
            db.commit()                                     # end the read txn before any LLM call
            outcome = score_answer(answer_in, question_in, deps.llm, max_calls=..., backoff_s=...,
                                   wait_before_call=throttled_wait, heartbeat=lambda: heartbeat(db, claim, now=deps.now()))
        except RunAborted: log("job=%s no longer ours, stopped"); return PROCESSED
        except RateLimited as e: requeue_rate_limited(db, claim, now=deps.now()); return RATE_LIMITED(e.retry_after)
        except Exception as e:                              # catch-all: never strand a claimed job
            db.rollback(); outcome = ScoringOutcome.failed(redact(f"unexpected error: {type(e).__name__}"))
        written = write_outcome(db, claim, outcome, now=deps.now())
        log.info("job=%s claim=%s status=%s written=%s", ..., "no longer ours" if not written else "")
        return PROCESSED
```
`throttled_wait(extra)`: sleep until `WORKER_MIN_CALL_INTERVAL_SECONDS` have passed since the last LLM call (by `deps.monotonic()`), plus `extra`. In-run retries go through the throttle as well.

```python
def run_forever(deps, stop: threading.Event):
    while not stop.is_set():
        try:
            r = run_once(deps)
        except OperationalError as e:            # e.g. database is locked past busy_timeout
            log.warning(...); stop.wait(5); continue
        except Exception:
            log.exception(...); stop.wait(5); continue   # worker keeps going
        if r is IDLE: stop.wait(WORKER_POLL_SECONDS)
        elif r is RATE_LIMITED: log(...); stop.wait(min(r.retry_after, MAX_PAUSE))
```

### `app/worker/__main__.py`
- `main(*, settings=None, session_factory=None, llm=None) -> int`. Defaults: `get_settings()`, `SessionLocal`, `GeminiScoringLLM(...)`. Tests inject all three.
- Logging: `basicConfig(INFO)` + a `logging.Filter` that replaces the API key value with `***` in messages and exception text.
- `PermanentLLMError` at construction (missing key) → stderr banner `worker: GEMINI_API_KEY is not set. Jobs stay queued. Set it in apps/api/.env and restart` → return 2. No DB access.
- Signals: the first SIGINT/SIGTERM sets `stop` (the current call finishes, the result is written, then exit). A second signal → `os._exit(130)`, and the lease (120s) recovers the job. Under `make dev`, Ctrl-C (SIGINT) followed by `kill 0` (SIGTERM) is two signals, so the worker exits at once and no orphan is left.
- `if __name__ == "__main__": sys.exit(main())`.

### Makefile
```make
worker:
	cd apps/api && uv run python -m app.worker
dev:   # third background process alongside api + web
	(cd apps/api && uv run python -m app.worker) &
```
Add `worker` to `.PHONY`. AGENTS.md command table gets a `make worker` row.

## Related Code Files
- Create: `apps/api/app/worker/__init__.py`, `job_queue.py`, `runner.py`, `__main__.py`
- Modify: `Makefile`, `AGENTS.md` (commands table)

## Implementation Steps
1. `job_queue.py` → `test_job_queue.py` green.
2. `runner.py` + `__main__.py` → `test_worker_runner.py` green.
3. Makefile + AGENTS.md.
4. Manual: `make seed`, set `GEMINI_API_KEY`, `make worker`, then watch the logs. `sqlite3 apps/api/data/app.db "select status,count(*) from scoring_jobs group by 1"` shows 0 queued/running at the end. Check A019, A007 and the 5 audio answers are needs_person and A022 is superseded.
5. Manual crash: `kill -9` the worker mid-job, restart, and within 120s the job is requeued and scored.
6. Manual signals: under `make dev`, Ctrl-C → `pgrep -f app.worker` is empty right away.
7. Full `uv run pytest`.

## Success Criteria
- [ ] Queue + runner suites green, unchanged
- [ ] Seeded data pack fully processed by the real worker, no `running`/`queued` left
- [ ] No orphan worker after Ctrl-C under `make dev`
- [ ] No transaction held open during an LLM call

## Risk Assessment
- SQLite `database is locked` under API + worker writes → WAL + busy_timeout, tiny writes, and `run_forever` backs off instead of dying.
- Lease 120s vs. the heartbeat gap: each call heartbeats first, and the gap ≤ timeout (30s) + backoff (4s) + throttle (4s) ≈ 38s, well under 120s. A hung SDK call past the timeout → recovered and re-claimed, and the fence drops the late write.
- `kill -9` between the LLM response and the write → recovered and re-scored (one extra call). Acceptable.
- A worker that is dead (exit 2 or a crash outside `run_forever`) under `make dev` isn't restarted. The banner and README note make this visible. No restart loop (YAGNI, the catch-all covers per-job failures).
