---
phase: 5
title: "HR actions: override, accept, retry + final docs"
status: done
priority: P1
dependencies: [4]
---

# Phase 5: HR actions: override, accept, retry + final docs

## Overview
Write endpoints for HR decisions and failed-job retry, safe under double clicks and concurrent candidate/worker writes. Then close out docs and gates. Done = `test_score_decisions.py`, `test_hr_actions_api.py`, `test_hr_permissions.py` (route-table), HR doc-coverage tests green, and the full gate green.

## Requirements
- Functional: override with reason (1–4); accept a `scored` suggestion; retry a failed job; latest decision counts; history kept.
- Non-functional: no duplicate rows from repeats or races; no decision stored on a replaced answer or a vanished suggestion; no FastAPI imports in the service; exact `detail` strings.

## Architecture

### `app/services/score_decisions.py`
```python
class AnswerNotFound(Exception); class AnswerSuperseded(Exception)
class NoSuggestion(Exception); class NeedsPersonReview(Exception); class SuggestionChanged(Exception)
class ConcurrentDecision(Exception)
class JobNotFound(Exception); class JobNotRetryable(Exception)

@dataclass
class DecisionResult: decision: ScoreDecision; created: bool
@dataclass
class RetryResult: job: ScoringJob; changed: bool

def record_decision(db, answer_id, *, kind: DecisionKind, score: int,
                    reason: str | None, hr_email: str) -> DecisionResult
def retry_job(db, job_id: int) -> RetryResult
```

`record_decision` flow:
0. Validate in the service too: `score` 1–4; override → `reason.strip()` non-blank and ≤ 2000; else `ValueError`. Accept forces `reason=None`. <!-- Red Team: integrity mapping -->
1. `answer = _load_answer(db, answer_id)` (keep this name: race tests patch it) → `AnswerNotFound`; `superseded_at` set → `AnswerSuperseded`.
2. Accept guard (`check_accept(job, score)`):
   - job `scored` and `suggested_score == score` → ok
   - job `scored`, different score → `SuggestionChanged`
   - job `needs_person` → `NeedsPersonReview` (user decision: a flagged score needs an override with a reason)
   - anything else → `NoSuggestion`
3. `latest = _latest_decision(db, answer_id)` (keep name). Same `(kind, score, reason, hr_email)` → `DecisionResult(latest, False)`.
4. Insert with `seq = (latest.sequence if latest else 0) + 1`, then `db.flush()`. pysqlite opens the write transaction at this INSERT. From here until commit, no other writer can commit.
5. **Re-check inside the write transaction** with a fresh query (`populate_existing`): answer still `superseded_at IS NULL`, else rollback → `AnswerSuperseded`. For accept, re-run `check_accept` on the freshly loaded job, else rollback → that exception. Then commit. This closes the check-then-act gap against a candidate re-answer or a retry that clears the suggestion. <!-- Red Team: check-then-act -->
6. `IntegrityError` on flush/commit → rollback. Then look up the row at `(answer_id, seq)`:
   - it exists with the same content → `(row, False)`
   - it exists with different content → `ConcurrentDecision`
   - **no such row → re-raise** (a real integrity bug, not a race)

Override is allowed for any job status, audio included. HR decides, and audio scoring is out of scope, so override is the only way to score an audio answer.

`retry_job` flow: <!-- Red Team: stale identity map -->
1. `job = db.get(ScoringJob, job_id)` → `JobNotFound`.
2. `res = db.execute(update(ScoringJob).where(ScoringJob.id == job_id, ScoringJob.status == "failed").values(status="queued", attempts=0, last_error=None, suggested_score=None, suggested_reason=None, needs_person_reason=None, finished_at=None, updated_at=utcnow()).execution_options(synchronize_session=False))`; commit.
3. `db.refresh(job)` (sessions use `expire_on_commit=False`, so without this the cached row is stale).
4. `res.rowcount == 1` → `RetryResult(job, True)`. Otherwise: refreshed `status == queued` → `RetryResult(job, False)` (double click); else → `JobNotRetryable`.

The bulk UPDATE skips ORM events but clears every score column in the same statement, so it satisfies `validate_job_result`. The worker plan picks queued jobs up. Until then a retried job stays `queued`, which is the honest state.

### Routes (`app/api/routes/hr_actions.py`, router-level `require_json_content_type` + `get_current_hr`)
| Method | Path | Body | Success | Errors |
|---|---|---|---|---|
| POST | `/api/hr/answers/{answer_id}/override` | `{score: int 1..4, reason: str}` (trimmed, non-blank, ≤ 2000) | 201 new / 200 identical repeat → `DecisionView` | 401, 404, 409, 415, 422 |
| POST | `/api/hr/answers/{answer_id}/accept` | `{score: int 1..4}` | 201 / 200 → `DecisionView` | 401, 404, 409, 415, 422 |
| POST | `/api/hr/jobs/{job_id}/retry` | `{}` (JSON required) | 200 → `JobView` (both changed and no-op) | 401, 404, 409, 415 |

`DecisionView` = `{id, answer_id, kind, score, reason, hr_email, created_at}`. `hr_email` comes from the session row (canonical `.env` email), never from the body. `ValueError` from the service can't occur via the API (pydantic validates first); if it does, it is a bug → 500.

### Fixed error `detail` strings (HR)
| Code | When | `detail` |
|---|---|---|
| 401 | missing / unknown / expired / revoked `hr_session` cookie (all HR routes) | `invalid or missing hr session` |
| 401 | sign-in with wrong email or password | `invalid email or password` |
| 503 | `HR_EMAIL` or `HR_PASSWORD` not set | `hr sign-in is not configured` |
| 404 | role id unknown | `role not found` |
| 404 | candidate id unknown | `candidate not found` |
| 404 | answer id unknown (override/accept) | `answer not found` |
| 404 | answer unknown, not audio, unmapped extension, or file missing | `audio not found` |
| 404 | job id unknown | `job not found` |
| 409 | override/accept on a superseded answer | `answer has been replaced by a newer submission` |
| 409 | accept with no suggested score | `no suggested score to accept` |
| 409 | accept on a `needs_person` answer | `needs a person: use override with a reason` |
| 409 | accept score ≠ current suggestion | `suggested score has changed, reload and try again` |
| 409 | concurrent different decision | `another decision for this answer was just saved, reload and try again` |
| 409 | retry on a non-failed, non-queued job | `only failed jobs can be retried` |
| 415 | HR `POST` without `Content-Type: application/json` | `content type must be application/json` |
| 422 | reason blank | `reason: must not be blank` |
| 422 | reason > 2000 chars | `reason: must be at most 2000 characters` |
| 422 | score out of range / missing, bad `status` filter, missing sign-in field | `<field>: <pydantic message>` (custom handler) |

### `test_api_doc_coverage.py`: `HR_EXPECTED_STATUS` (separate from candidate dicts)
| Route | Codes |
|---|---|
| POST `/api/hr/session` | 200, 401, 415, 422, 503 |
| GET `/api/hr/session` | 200, 401 |
| DELETE `/api/hr/session` | 204 |
| GET `/api/hr/roles` | 200, 401 |
| GET `/api/hr/roles/{role_id}/candidates` | 200, 401, 404 |
| GET `/api/hr/candidates/{candidate_id}` | 200, 401, 404 |
| GET `/api/hr/jobs` | 200, 401, 422 |
| GET `/api/hr/answers/{answer_id}/audio` | 200, 206, 401, 404, 416 |
| POST `/api/hr/answers/{answer_id}/override` | 201, 200, 401, 404, 409, 415, 422 |
| POST `/api/hr/answers/{answer_id}/accept` | 201, 200, 401, 404, 409, 415, 422 |
| POST `/api/hr/jobs/{job_id}/retry` | 200, 401, 404, 409, 415 |

`HR_EXPECTED_DETAILS`: each route → its exact `detail` strings from the table above (backticked in the doc). Codes are matched against table rows or `**Response <code>**` headings, not substrings. Every section contains `**Auth:**`, `**Request:**`, `**Errors:**` and a fenced `json` block (the audio and DELETE sections use the error example).

### Final docs
- `docs/api-doc.md`: 3 action sections (full checklist). Behaviour notes: append-only history, identical repeat = 200, accept guard incl. `needs_person`, retry semantics, JSON content-type rule.
- `apps/web/src/lib/api-types.ts`: `OverrideRequest`, `AcceptRequest`, `RetryRequest` (`Record<string, never>`), `DecisionView`, `DecisionKind`.
- `docs/architecture.md`:
  - data model additions (`hr_sessions` incl. fingerprint, `score_decisions`, job result columns)
  - job result invariants are **ORM-enforced, not DB CHECKs**, why, plus the read-side gate
  - HR auth model: MOCK; cookie only; why candidate tokens can't cross over; revocation on account change; demo default password is live after `make setup` (accepted risk, change it for any shared setup)
  - CSRF: JSON content-type + no CORS, so cross-origin requests fail preflight (not "SameSite alone")
  - final-score rule (`scored` only; `needs_person` needs an HR override)
  - answer lifecycle extended with HR decisions, retry, and "resubmission starts a fresh final score; earlier decisions stay visible"
  - **worker contract:** claim with `UPDATE … WHERE status='queued'`; write results only `WHERE status='running'` and only after calling `validate_job_result`; on failure clear every score column in the same statement
  - "not built": rate limiting, CSRF tokens, multi-user HR, session sweeping, "Read first" ordering, "Load data pack" button, tighter candidate upload content-type allow-list
- `README.md`: "HR sign-in (MOCK)" with creds from `apps/api/.env`, how to change them (changing them signs everyone out); existing `.env` files need the new vars.

## Related Code Files
- Create: `apps/api/app/services/score_decisions.py`
- Create: `apps/api/app/api/routes/hr_actions.py`
- Modify: `apps/api/app/schemas/hr.py`: `OverrideRequest`, `AcceptRequest`, `RetryRequest`, `DecisionView`
- Modify: `apps/api/app/main.py`: include router
- Modify: `docs/api-doc.md`, `apps/web/src/lib/api-types.ts`, `docs/architecture.md`, `README.md`

## Implementation Steps
1. Service → `test_score_decisions.py` green (all race tests).
2. Schemas + routes + error mapping → `test_hr_actions_api.py` green; `test_hr_permissions.py` route-table test green (all 9 guarded routes exist).
3. Docs + types + architecture + README → HR doc-coverage tests green.
4. Manual smoke:
   - `make seed`, `make dev`
   - curl sign-in (`-c jar`), `GET /api/hr/roles`, a candidate review, override (JSON), retry on a job set to failed via sqlite3, audio fetch (check headers)
   - candidate Bearer on `/api/hr/roles` → 401
   - form-encoded override → 415
5. Full gate: `make lint && make test`; `cd apps/api && uv run alembic check`.

## Success Criteria
- [ ] All HR suites green with no test edits; candidate suites still green
- [ ] No duplicate decision rows; no decision stored on a superseded answer or vanished suggestion (race tests)
- [ ] `docs/api-doc.md` covers all 11 HR routes with exact `detail` strings (enforced by `HR_EXPECTED_DETAILS`)
- [ ] `make lint && make test` green; `alembic check` clean

## Risk Assessment
- Retry vs. worker race: covered by the worker contract above (conditional claims and writes).
- Override while a job is `queued`/`running`: the override wins in `final_score` even after the worker scores. Documented.
- If pysqlite's implicit-transaction behaviour changes (e.g. `autocommit` settings), the step-5 re-check still runs before commit but loses its lock guarantee. Pinned by the supersede-race test.
