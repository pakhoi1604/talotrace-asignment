# Red team: failure mode analyst / flow tracer, LLM scoring worker plan

Scope: plan.md and phases 01-04 of `plans/261102-1549-llm-scoring-worker`, checked against current code (`apps/api/app/**`, `tests/conftest.py`, `Makefile`, data pack) and the blocking HR plan (`plans/261102-1531-hr-review-api` phases 02 and 05).
Empirical check (scratch script, nothing in the repo changed): SQLite `DateTime(timezone=True)` round-trip and Core `update()` onupdate behaviour on the real `ScoringJob` model.

## Finding 1: An unexpected exception kills the worker and leaves the job `running` with nobody left to recover it
- **Severity:** Critical
- **Location:** Phase 3, section "`app/worker/runner.py`". Phase 2, sections "Gemini client" and "Decision function"
- **Flaw:** The only exceptions handled anywhere are `LLMRefusal`, `PermanentLLMError`, `TransientLLMError` and `InvalidModelOutput`. The client only maps `errors.ClientError`, `errors.ServerError` and `httpx` timeout/transport errors. `run_once` and `run_forever` have no catch-all. Some things that escape:
  - `google.genai.errors.APIError` for codes that are neither 4xx nor 5xx
  - `ValueError` from the SDK when it turns the `ModelScore` Pydantic model into a `response_schema`. That fails on every call, so every job is affected
  - `AttributeError`/`TypeError` when reading `finish_reason` from `resp.candidates` while it is `None`
  - `sqlite3.OperationalError: database is locked` from `bump_attempt` or `write_outcome` once the 5s busy timeout runs out
  
  Any of these goes straight up out of `run_forever`, and the process exits.
- **Failure scenario:** The SDK rejects the schema conversion on the first job. The worker dies in its first second under `make dev`. The job stays `running` (the claim was committed). `wait` keeps api and web up, so the UI looks healthy. Nothing ever runs `recover_stale_jobs` because the only process that runs it is dead. HR sees 1 job `running` and 34 `queued`, forever. That is the opposite of "failures end in a clear state".
- **Evidence:**
  - `plans/261102-1549-llm-scoring-worker/phase-02-scorer-core.md:69`: `except errors.ClientError as e: raise (Transient if e.code in (408, 429) else Permanent)` (no generic `APIError` or `Exception` branch)
  - `phase-02-scorer-core.md:87-89`: only `LLMRefusal`, `PermanentLLMError`, `(TransientLLMError, InvalidModelOutput)` are caught
  - `phase-03-job-queue-and-worker-process.md:50-61`: `run_once` has no try/except around `score_answer` or `write_outcome`
  - `phase-03-job-queue-and-worker-process.md:63-67`: `run_forever` loop has no guard
  - `apps/api/app/db/session.py:112`: `PRAGMA busy_timeout=5000`, so a lock wait longer than 5s raises
  - `phase-01-write-failing-scorer-tests-first.md:79-89`: no test where the fake raises `RuntimeError`/`ValueError`
- **Suggested fix:**
  - In `run_once`, wrap scoring in `except Exception as e`. Build a fenced `failed` outcome with `last_error=f"internal error: {type(e).__name__}: {redact(e)}"`, log it with the traceback, and return True.
  - In `run_forever`, catch `OperationalError` and other DB errors, log them, and wait for `stop.wait(poll)` instead of exiting.
  - Phase 1 test: a fake that raises `RuntimeError` → job `failed` with `last_error`, and the next `run_once` still processes the next job.

## Finding 2: Poison jobs loop forever because `attempts` is only bumped by LLM calls
- **Severity:** Critical
- **Location:** Phase 3, section "`job_queue.py`" (`recover_stale_jobs`). Phase 2, section "Decision function". plan.md "Crash recovery"
- **Flaw:**
  - Stale recovery only moves a job to `failed` when `attempts >= max_attempts`. `attempts` is incremented only by `on_attempt()` just before an LLM call. The claim doesn't bump it, and neither do the snapshot/lazy-load, the audio path, the pre-scan path or `write_outcome`.
  - A job that crashes the worker before its first LLM call, or after the call but in `write_outcome`, keeps `attempts` where it was. Recovery sends it back to `queued` every lease period with no limit.
  - The reverse problem: `attempts` is never reset on requeue, while `score_answer` runs `max_attempts` calls per claim. So `SCORER_MAX_ATTEMPTS=3` is not a total cap. A job requeued at attempts=2 gets 3 more calls (attempts=5).
- **Failure scenario:**
  - An audio answer whose snapshot raises (missing question row, unexpected `None`) crashes the worker (Finding 1).
  - On restart, after 600s it is requeued with attempts=0, claimed, and crashes again, forever.
  - Each cycle blocks scoring for everyone else for the length of the crash and restart.
  - If the crash is caught instead, the job is never marked failed by recovery. It ping-pongs between `running` and `queued`.
- **Evidence:**
  - `phase-03-job-queue-and-worker-process.md:22-29`: claim sets `status="running", updated_at=now` (no `attempts` bump)
  - `phase-03-job-queue-and-worker-process.md:42-44`: `... AND attempts >= max_attempts` → failed, else `SET status='queued'`
  - `phase-02-scorer-core.md:79-82`: the audio and pre-scan returns happen before `on_attempt()`
  - `plan.md:29`: "or to `failed` ... once attempts are used up"
- **Suggested fix:**
  - Count claims, not LLM calls, for the poison cap. Bump `attempts` in the claim UPDATE (`attempts = attempts + 1`), and keep LLM-call retries as a local counter in `score_answer`. Alternatively, keep `attempts` per call but have recovery use `attempts >= max_attempts OR <claims counted in updated_at/last_error>`. Simplest is the claim bump.
  - Phase 1 test: a job whose processing raises before any LLM call ends `failed` after N recoveries, not requeued forever.

## Finding 3: Systemic errors (bad key or model, quota 429) are charged to individual jobs, so one misconfiguration turns the whole queue `failed`
- **Severity:** High
- **Location:** plan.md "Retries", "Rate limit", "Open questions". Phase 2, sections "Decision function" and "Gemini client"
- **Flaw:**
  - A permanent 400/401/403/404 fails the current job and the worker moves on to the next, which fails the same way.
  - 429 is treated as a per-job transient error with 2s/4s backoff. Free-tier quota errors are per minute or per day and carry a `retryDelay` of tens of seconds. Retries inside a job also skip the 4s min interval: the throttle only runs between `run_once` calls, and the backoff is shorter than it.
  - The HR plan only offers single-job retry (`retry_job(db, job_id)`, no bulk retry).
- **Failure scenarios:**
  - (a) `GEMINI_MODEL=gemini-3.5-flash-lite` 404s (the plan itself lists this as an open question). Within a minute all 29 current text jobs are `failed`. Fixing `.env` doesn't requeue them, so HR must click retry 29 times.
  - (b) A per-minute or daily quota is hit mid-pack. Each later job burns 3 calls in ~6s and fails, and the failures cascade through the queue. The extra calls make the quota problem worse.
- **Evidence:**
  - `plan.md:27`: "Permanent errors (400/401/403/404, i.e. bad key or bad model) → `failed` at once"
  - `plan.md:31`: `WORKER_MIN_CALL_INTERVAL_SECONDS`=4
  - `plan.md:72`: "If it 404s, it fails fast as a permanent error ... only `.env` needs to change"
  - `phase-02-scorer-core.md:24`: `SCORER_BACKOFF_SECONDS: float = 2  # 2s, then 4s`
  - `phase-02-scorer-core.md:89`: backoff `sleep(backoff * 2**(attempt-1))`
  - `phase-03-job-queue-and-worker-process.md:66-69`: throttle only in `run_forever`
  - `plans/261102-1531-hr-review-api/phase-05-hr-actions-and-docs.md:34`: `def retry_job(db, job_id: int)`
- **Suggested fix:**
  - Split "job-level" errors (invalid output, refusal, 5xx) from "worker-level" errors (401/403/404 model or key, 429).
  - For worker-level errors, don't write an outcome. Put the job back with a conditional `UPDATE ... SET status='queued' WHERE status='running'` without spending attempts, then pause the worker: honour `retryDelay` for 429, and exit non-zero with a clear stderr message for 401/403/404.
  - Make in-job retries go through the same min-interval throttle.
  - Tests: 404 on job 1 leaves jobs 2..N `queued`. 429 doesn't fail the job.

## Finding 4: Worker death is invisible and never restarted under `make dev`, and Ctrl-C leaves an orphan worker running
- **Severity:** High
- **Location:** Phase 3, sections "Makefile" and "`app/worker/__main__.py`". plan.md "Missing API key"
- **Flaw:**
  - `make dev` uses `wait` with no supervision. If the worker exits (missing key, exit code 2, or any crash from Finding 1), api and web keep running. The one stderr line is buried under Next/uvicorn output, and nothing in the product shows that no worker is alive. "Jobs stay queued (honest state)" looks exactly like a busy worker.
  - On Ctrl-C, `trap 'kill 0'` sends SIGTERM to the whole group. The plan's SIGTERM handling is "finish the current job", which can take ~96s (3×30s timeout + 6s backoff). `make` returns the prompt while the worker keeps writing to the terminal. A quick `make dev` restart then runs two workers at once, which is the precondition for Finding 5.
- **Failure scenario:** An evaluator follows the README without a key, or with a typo in the key name. `make dev` is "up", the candidate flow works, and the HR area shows every job `queued` with no hint why. Graders read that as scoring being broken.
- **Evidence:**
  - `Makefile:207-211`: `@trap 'kill 0' INT TERM; ... & ... & wait`
  - `phase-03-job-queue-and-worker-process.md:72-73`: exit 2 on missing key; "SIGINT/SIGTERM → `stop.set()`. The current job finishes or its lease expires."
  - `phase-03-job-queue-and-worker-process.md:80-81`: the worker is added as a plain third `&` process
  - `plan.md:30`: "Worker exits non-zero at startup ... Jobs stay `queued` (honest state). API + web keep running"
- **Suggested fix:**
  - Make `make dev` fail loudly: check the key before starting all three processes and print a banner. Alternatively, wrap the worker in `until uv run python -m app.worker; do echo "worker exited, restarting in 5s"; sleep 5; done` for crashes (exit code 2 stops the loop).
  - On the second signal, or after a short grace period, abort the in-flight call. The fenced write plus recovery already cover an abandoned job.
  - Document in README that `queued` with no movement means no worker is running.

## Finding 5: The write fence is status-only, so a stalled worker's late heartbeat or write lands on another claim of the same job (ABA through stale recovery and HR retry)
- **Severity:** Medium
- **Location:** Phase 3, section "`job_queue.py`" (`bump_attempt`, `write_outcome`). plan.md "Write fencing". Phase 3 "Risk Assessment"
- **Flaw:** `WHERE id=:id AND status='running'` doesn't tell this worker's claim apart from a later claim. `running` can come back through `running → queued (stale) → running`, or through `running → failed (stale, attempts used) → queued (HR retry_job resets attempts=0) → running`.
- **Failure scenario:**
  1. Worker A (an orphan from Finding 4, a second `make worker`, or a process stalled by laptop suspend while another worker runs) holds job 7 for more than 600s.
  2. Worker B recovers job 7 to `failed`. HR retries it, and B claims it.
  3. A finally returns `failed: gave up ...`. Its `write_outcome` matches `status='running'` and commits `failed` over B's live claim.
  4. B's later good `scored` write gets rowcount 0, and B logs it as "superseded mid-run".
  
  The final state is `failed` even though a valid score was produced, the log is wrong, and A's late `bump_attempt` calls have also been changing B's `attempts`.
- **Evidence:**
  - `phase-03-job-queue-and-worker-process.md:31-38`: both writes are fenced on `status='running'` only. "rowcount 0 → superseded mid-run"
  - `phase-03-job-queue-and-worker-process.md:107`: "the fenced write still keeps one result" (it keeps the wrong one)
  - `plans/261102-1531-hr-review-api/phase-05-hr-actions-and-docs.md:57`: retry sets `status="queued", attempts=0`, so `attempts` can't serve as a token either
- **Suggested fix:** Fence on a claim token. No schema change is needed: claim with `updated_at = :claim_ts`. Every heartbeat and write uses `WHERE id AND status='running' AND updated_at = :my_last_ts`, and each heartbeat moves `my_last_ts` forward. Alternatively, add a `claim_id` column via autogenerate. Log "rowcount 0: job no longer owned (superseded/recovered)", not "superseded".

## Finding 6: `on_attempt()`'s result is ignored, so a job superseded mid-run keeps spending LLM calls, and a failed heartbeat goes unnoticed
- **Severity:** Medium
- **Location:** Phase 2, section "Decision function". Phase 3, section "`app/worker/runner.py`"
- **Flaw:**
  - `bump_attempt` returns False when the job has stopped being `running` (superseded or recovered), but `score_answer` calls `on_attempt()` and throws the result away.
  - If `bump_attempt` raises (`database is locked`), the exception escapes `score_answer` (Finding 1).
- **Failure scenario:** A candidate replaces an answer while its job is in transient retry. The worker still makes up to 2 more Gemini calls and sleeps 6s of backoff on a dead job, using free-tier quota (Finding 3) and holding up the queue, only to have the write discarded.
- **Evidence:**
  - `phase-02-scorer-core.md:82`: `on_attempt()                       # worker bumps attempts (heartbeat)`
  - `phase-03-job-queue-and-worker-process.md:58`: `on_attempt=lambda: bump_attempt(db, job_id, now=clock())`
  - `phase-03-job-queue-and-worker-process.md:31-32`: bump is fenced on `status='running'` and returns bool
- **Suggested fix:** `on_attempt() -> bool`. On False, `score_answer` raises or returns an `Abandoned` sentinel, and `run_once` skips the write and logs "no longer owned". Phase 1 test: supersede during the first transient failure → exactly 1 LLM call.

## Finding 7: The clock contract is undefined, and SQLite drops tzinfo, so stale detection and timestamps are unsafe
- **Severity:** Medium
- **Location:** Phase 1, section "interfaces the tests pin" (`clock`). Phase 3, sections "`job_queue.py`" (`recover_stale_jobs`) and "`run_forever`"
- **Flaw:**
  - (a) `cutoff = now - lease_s` subtracts an int from a datetime (`TypeError`).
  - (b) `run_forever` uses a float clock (`last_call = 0.0`) while the DB needs datetimes, and `run_once(..., clock)` doesn't say which one it gets.
  - (c) Verified empirically: SQLAlchemy SQLite `DateTime(timezone=True)` stores wall-clock text with no offset. A job stamped `12:00Z` matched `updated_at < 18:30+07:00` (11:30Z), so a non-UTC aware or naive-local clock silently shifts the lease by the UTC offset. Values also read back naive, so any Python comparison with `utcnow()` raises `TypeError`.
  - (d) Verified: a Core `update()` that doesn't set `updated_at` fires `onupdate=utcnow` with the real clock. The planned requeue and `failed` recovery UPDATEs stamp real time, not the injected `now`.
- **Failure scenario:**
  - A developer in UTC+7 injects `datetime.now` (naive local). Every running job looks 7h old. A second worker or an orphan requeues live jobs (Finding 5).
  - Tests using a fixed fake clock get real-time `updated_at` after recovery, so the "fresh running is untouched" and "attempts ≥ max → failed" assertions depend on the wall clock. The usual result is that someone weakens the test.
- **Evidence:**
  - `apps/api/app/models/scoring_job.py:29-31`: `updated_at ... DateTime(timezone=True), default=utcnow, onupdate=utcnow`
  - `apps/api/app/core/time.py:4-5`: `datetime.now(UTC)`
  - `phase-03-job-queue-and-worker-process.md:41-44`: `cutoff = now - lease_s`, and the requeue UPDATE sets no `updated_at`
  - `phase-03-job-queue-and-worker-process.md:64`: `last_call = 0.0`
  - `phase-01-write-failing-scorer-tests-first.md:58`: `run_once(..., *, sleep, clock)` (type unspecified)
  - Empirical output: `raw: 2026-01-01 12:00:00.000000`, `readback: datetime(2026,1,1,12,0)` (naive), "aware non-UTC cutoff matches: 1"; after a Core update without `updated_at`: `2026-11-02 09:02:16` (real now)
- **Suggested fix:**
  - Pin `clock: Callable[[], datetime]` returning aware UTC, and assert `now.utcoffset() == timedelta(0)` in `job_queue`.
  - Use `timedelta(seconds=lease_s)`, and a separate `monotonic` for the throttle.
  - Set `updated_at=now` (and `finished_at=now`) explicitly in every bulk UPDATE, including both recovery statements.

## Finding 8: Data-pack traps aren't handled, and the acceptance count is wrong (A007 blank, A022 superseded)
- **Severity:** Medium
- **Location:** plan.md "Acceptance criteria". Phase 2, section "Decision function". Phase 4 "Live tests"
- **Flaw:**
  - A007 has `"transcript": ""` (duration 0). The parser accepts it as a text answer, so the worker sends an empty `<answer-…>` block to Gemini. The model's result is unpredictable: it might return 1, refuse, or produce invalid JSON. There is no deterministic route for it and no test.
  - A022 and A023 are the same candidate and question (C2052, Q3). The seed imports in `submitted_at` order, so A022 always ends `superseded`. The criterion "all 30 typed data-pack answers reach `scored`/`needs_person`" can't be met. An implementer chasing it may "fix" the seed or the supersede logic.
- **Failure scenario:** The live demo shows A007, an empty answer, as "suggested 1, reason: the candidate described…", which is a hallucination. Or it comes out `failed` after 3 invalid outputs, so HR sees a retryable failure that never succeeds.
- **Evidence:**
  - `business-systems-pack/answers/A007.json`: `"duration_seconds": 0, "transcript": ""`
  - `apps/api/app/seed/data_pack_parser.py:132-135`: only `None` vs present is checked
  - `apps/api/app/seed/runner.py:182`: imports sorted by `(submitted_at, answer_id)`
  - `apps/api/app/services/answer_submission.py:105-109`: earlier answer and job set to `SUPERSEDED`
  - `plans/261102-1549-llm-scoring-worker/plan.md:53`: "all 30 typed data-pack answers reach `scored`/`needs_person`"
  - `phase-02-scorer-core.md:79-80`: only the audio and pre-scan short-circuits exist
- **Suggested fix:**
  - Add a deterministic branch: a blank or whitespace-only text answer → `needs_person("answer is blank")` with no LLM call. Alternatively, a deterministic score of 1 with a fixed reason, but that is a user decision, so ask.
  - Restate the acceptance as 29 current typed answers → `scored`/`needs_person` and A022 → `superseded`.
  - Add both to the phase 1 data-pack regression test.

## Finding 9: The key concurrency and startup tests are phantom or environment-dependent
- **Severity:** Medium
- **Location:** Phase 1, sections "job_queue" and "worker_runner"
- **Flaw:**
  - "Two sessions claim at once → second conditional UPDATE rowcount 0" can't happen in a single-threaded test. If session A claims and commits first, B's SELECT already skips the job, so the lost-race branch at `rowcount != 1 → try next` never runs. The plan defines no hook to force the stale read, unlike the existing `_load_current_answer` pattern.
  - The "missing `GEMINI_API_KEY` → `main()` exits 2" test goes through `get_settings()`, which reads `.env` from the CWD. Tests run from `apps/api`, so on a dev machine with a real key in `apps/api/.env`, `main()` builds a real client and drops into `run_forever`, and the test hangs.
- **Failure scenario:** The suite is green while the claim loop's lost-race path is untested (an infinite-loop or off-by-one there ships). On the author's machine, with a key set, `make test` hangs or reaches the network, which breaks the "no network" requirement.
- **Evidence:**
  - `phase-01-write-failing-scorer-tests-first.md:95`: "two sessions claim at once → exactly one gets the job (second conditional UPDATE rowcount 0 ...)"
  - `phase-01-write-failing-scorer-tests-first.md:102`: "Missing `GEMINI_API_KEY` → `main()` exits code 2"
  - `apps/api/app/core/config.py:145`: `SettingsConfigDict(env_file=".env", ...)`
  - `apps/api/app/core/config.py:157-159`: `@lru_cache get_settings()`
  - `apps/api/app/services/answer_submission.py:55-56`: "Private hook: the race test patches this to simulate a stale read"
- **Suggested fix:**
  - Add a private `_next_queued_id(db)` hook to `claim_next_job` and patch it in the race test to return an id that another session has already claimed. Assert one winner and no infinite loop.
  - Have `main(settings: Settings | None = None)` take settings by injection, and build the test's `Settings(_env_file=None, GEMINI_API_KEY=None)`.

---
Status: DONE_WITH_CONCERNS
Summary: The plan's happy path and supersede fence trace correctly through `record_answer` and the HR `retry_job`. But an unexpected exception kills the worker and strands jobs (Findings 1, 2, 4), systemic Gemini errors mass-fail the queue (Finding 3), and the status-only fence allows ABA overwrites across recovery and retry (Finding 5).

Unresolved questions:
- Blank answer (A007): `needs_person` or a deterministic score of 1? This is a product decision for the user.
- Should worker-level config errors (404 model, 401 key) stop the worker, or mark jobs failed? The plan locked "failed at once", so reversing it needs user sign-off.
