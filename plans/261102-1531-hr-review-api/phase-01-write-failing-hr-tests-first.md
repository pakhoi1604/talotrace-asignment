---
phase: 1
title: "Write failing tests first"
status: done
priority: P1
dependencies: []
---

# Phase 1: Write failing tests first

## Overview
Write the full HR test suite before any implementation, against the contracts in phases 2–5. End state: HR tests are collected and fail for the expected reason (ImportError / missing route / missing table / missing doc section). Phases 2–5 make them green. Candidate-plan tests stay green throughout.

## Requirements
- Tests use only contracts in this plan (module paths, signatures, routes, status codes, `detail` strings, response shapes).
- One behaviour per test, descriptive names, no plan/phase IDs.
- Real SQLite in `tmp_path`; no mocks of our own code except the named stale-read hooks (`_latest_decision`, `_load_answer`) and a second session for job races.
- **Settings isolation:** every test `Settings` is built with `_env_file=None` and pins all HR fields explicitly, so a developer's `apps/api/.env` can't change results. <!-- Red Team: tests read dev .env -->
- Later phases must not weaken tests. A test changes only if it contradicts the plan's contract; say why in the commit.

## Contracts the tests rely on
| Contract | Defined in |
|---|---|
| `app.models`: `HrSession` (with `credential_fingerprint`), `ScoreDecision`; `ScoringJob` result columns; `app.models.enums.DecisionKind`; `app.models.scoring_job.validate_job_result(status, score, reason, needs_person_reason)` raising `ValueError` (also run on flush) | Phase 2 |
| Settings: `HR_EMAIL`, `HR_PASSWORD` (blank → `None`), `HR_SESSION_TTL_HOURS`, `HR_COOKIE_SECURE` | Phase 2 |
| `app.services.hr_auth`: `verify_credentials(settings, email, password) -> bool`, `credential_fingerprint(settings) -> str \| None`, `create_session(db, settings) -> str`, `find_session(db, raw, settings) -> HrSession \| None`, `delete_session(db, raw) -> None` | Phase 3 |
| Routes `POST/GET/DELETE /api/hr/session`; cookie `hr_session`; `app.api.deps.get_current_hr` (returns `HrSession`), `app.api.deps.require_json_content_type` | Phase 3 |
| `app.schemas.common.UtcDatetime` (serialises with `Z`/`+00:00`, attaches UTC to naive values) | Phase 4 |
| `app.services.hr_review`: `visible_suggestion(job) -> tuple[int \| None, str \| None]`, `final_score(answer) -> tuple[int \| None, "hr" \| "suggested" \| None]` | Phase 4 |
| Read routes (roles, candidates, candidate review, jobs, audio) | Phase 4 |
| `app.services.score_decisions`: `record_decision(db, answer_id, *, kind, score, reason, hr_email) -> DecisionResult`, `retry_job(db, job_id) -> RetryResult`, exceptions `AnswerNotFound`, `AnswerSuperseded`, `NoSuggestion`, `NeedsPersonReview`, `SuggestionChanged`, `ConcurrentDecision`, `JobNotFound`, `JobNotRetryable`; private hooks `_latest_decision`, `_load_answer` | Phase 5 |
| Action routes (override, accept, retry) | Phase 5 |

## Related Code Files
- Modify: `apps/api/tests/conftest.py`: fixture `test_settings(upload_dir)` = `Settings(_env_file=None, UPLOAD_DIR=..., MAX_AUDIO_BYTES=1024, HR_EMAIL="hr@test.local", HR_PASSWORD="pw", HR_COOKIE_SECURE=False, HR_SESSION_TTL_HOURS=12)`; `client` override returns it; fixture `hr_client(client)` signs in and returns the same client (cookie jar set)
- Modify: `apps/api/tests/factories.py`: `set_job_result(db, answer, *, status, score=None, reason=None, needs_person_reason=None)`, `add_decision(...)`, `make_audio_answer(db, candidate, question_id, upload_dir, ext=".m4a", content_type="audio/mp4")`
- Create: `apps/api/tests/route_table.py`: `api_routes(app) -> list[APIRoute-with-full-path]`, **recursing** into Starlette 1.10 `_IncludedRouter.original_router` with `include_context.prefix` (moved from `test_api_doc_coverage._api_routes`). <!-- Red Team: route enumeration empty -->
- Modify: `apps/api/tests/test_api_doc_coverage.py`: import `api_routes` from `route_table` (refactor only, candidate assertions untouched); add **separate** HR tests driven by `HR_EXPECTED_STATUS` + `HR_EXPECTED_DETAILS` (phase 5 tables). HR status codes matched against a table row (`^\|\s*<code>\s*\|`) or a `**Response <code>**` heading, not a raw substring. <!-- Red Team: doc coverage weak -->
- Create: `apps/api/tests/test_hr_models.py`, `test_hr_auth.py`, `test_hr_permissions.py`, `test_hr_read_api.py`, `test_hr_actions_api.py`, `test_score_decisions.py`

## Test cases

### `test_hr_models.py`
- two `ScoreDecision` rows with same `(answer_id, sequence)` → `IntegrityError`
- decision `score` 0 or 5 → `IntegrityError`; invalid `kind` → `IntegrityError`; `kind=override` with `reason=None` → `IntegrityError`
- `HrSession.token_hash` unique
- `validate_job_result` + flush:
  - `failed` / `queued` / `running` with `suggested_score=2` → `ValueError`
  - `scored` without score or without reason → `ValueError`
  - `suggested_score` 0 or 5 → `ValueError`
  - `needs_person` without `needs_person_reason` → `ValueError`
  - valid `scored` (3 + reason), valid `needs_person` (2 + reasons), and `superseded` keeping its score → flush OK

### `test_hr_auth.py`
- `verify_credentials`: right pair → True; wrong password / wrong email → False; email trimmed + case-insensitive; `HR_PASSWORD=None` → False; `Settings(_env_file=None, HR_PASSWORD="  ")` loads as `None`
- `create_session` stores only sha256 of the raw token, `email == settings.HR_EMAIL` (canonical, not the typed casing), and the current `credential_fingerprint`
- `find_session` **from a second session** (fresh load, naive datetimes from SQLite) → row; unknown → None; expired → None. No `TypeError`. <!-- Red Team: naive datetimes -->
- `find_session` after `HR_PASSWORD` changed in settings → None; after `HR_EMAIL` changed → None; with creds unset → None. <!-- Red Team: session revocation -->
- `delete_session` → `find_session` None
- API `POST /api/hr/session` right creds → 200 `{email, expires_at}`, `expires_at` string ends with `Z` or `+00:00`; `Set-Cookie` contains `hr_session`, `httponly`, `samesite=lax`, `path=/` (**case-insensitive**)
- signing in as `" HR@Test.Local "` → 200 and `email == "hr@test.local"`
- wrong creds → 401 `invalid email or password`, no cookie
- missing field → 422 `email: Field required`
- body sent as `text/plain` → 415 `content type must be application/json`
- creds explicitly `None` in settings → 503 `hr sign-in is not configured`
- `GET /api/hr/session` → 200 `{email, expires_at}` with UTC suffix; no cookie → 401 `invalid or missing hr session`
- `DELETE /api/hr/session` → 204 with empty body, cookie cleared; a **second `TestClient`** with `cookies.set("hr_session", old)` then → 401; DELETE without cookie → 204

### `test_hr_permissions.py`
- **route-table test:** `api_routes(create_app())` filtered to paths starting `/api/hr/`, minus `POST /api/hr/session` and `DELETE /api/hr/session`. For each: (a) the route's dependant tree contains `get_current_hr`; (b) calling it with no cookie → 401 `invalid or missing hr session`; (c) calling it with only `Authorization: Bearer <valid candidate token>` → 401 same detail. Path params filled from seeded ids. Guard: exactly the 9 guarded routes from `plan.md`'s endpoint table (set equality, so a missing or extra route fails loudly). **Goes green only in phase 5.**
- candidate endpoints with only a valid HR cookie → 401 `invalid or missing candidate token`
- forged cookie value → 401

### `test_hr_read_api.py` (via `hr_client`)
Setup: 2 roles, role A has 2 candidates, 6 synthetic questions.
- `GET /api/hr/roles` → both roles, `candidate_count`, `job_counts` keys `queued, running, scored, failed, needs_person` (superseded never counted)
- `GET /api/hr/roles/{id}/candidates` → only that role, sorted by name; fields per phase 4; unknown → 404 `role not found`
- averages: scored 3 + scored 2 + failed + needs_person(score 2) → `avg_suggested == 2.5` (**only `scored` counts**); override scored-2 → 4 → `avg_final == 3.5`; nothing scored → both `null`
- `GET /api/hr/candidates/{id}` → 6 entries in position order with `rubric`; unanswered → `answer: null`
- text answer entry fields per phase 4; all `*_at` strings end with `Z` or `+00:00`
- **duplicates:** answer replaced once → `answer` is newest; `earlier_submissions` has the old one with `superseded_at`; `submission_count == 2`; old job not in `job_counts`
- **decision survives resubmission:** override on Q1, candidate replaces Q1 → new answer `decisions == []`, `final_source == "suggested"` or null; `earlier_submissions[0].decisions` holds the override. <!-- Red Team: orphaned decisions -->
- **failed job:** `job.status == "failed"`, `job.suggested_score is None`, `final_score is None`, `last_error` present
- **ORM bypass:** raw SQL `UPDATE scoring_jobs SET status='failed', suggested_score=2` → review shows `job.suggested_score is None`, `final_score is None`, average excludes it. <!-- Red Team: read-side gating -->
- needs_person with suggested 2 → `job.suggested_score == 2`, `final_score is None` until a decision
- decisions newest first with `kind, score, reason, hr_email, created_at`; `final_source == "hr"`
- audio entry: `text is None`, `audio == {content_type, size_bytes, url: "/api/hr/answers/<id>/audio"}`
- unknown candidate → 404 `candidate not found`
- `GET /api/hr/jobs` → current jobs only, newest `updated_at` first, with `candidate`, `role`, `answer{id, kind, question_id}`; `counts` for all 6 statuses; `?status=failed` → only failed; `?status=superseded` → superseded; `?status=bogus` → 422 starting `status:`
- `GET /api/hr/answers/{id}/audio` (.m4a) → 200, body == file bytes, `content-type` == `audio/mp4` (**from extension map**), `x-content-type-options: nosniff`, `content-security-policy` contains `sandbox`
- **hostile stored type:** audio row with `audio_content_type="audio/x, text/html"` and `.m4a` path → response `content-type` is `audio/mp4`. <!-- Red Team: stored XSS -->
- `Range: bytes=0-3` → 206 with 4 bytes
- text answer → 404 `audio not found`; unknown id → 404; file deleted → 404; `audio_path="../escape.m4a"` → 404; path with unmapped extension → 404
- relative `UPLOAD_DIR` (settings `UPLOAD_DIR="uploads"`, file placed under `resolve_api_path("uploads")`) → 200

### `test_score_decisions.py` (service)
- override on current answer → `created=True`, `sequence=1`, `hr_email` stored
- identical override again → `created=False`, same row; different override → `sequence=2`, newest counts in `final_score`
- override on superseded → `AnswerSuperseded`; unknown → `AnswerNotFound`; `score=5` or blank reason → `ValueError` (service validates too)
- override allowed for job `queued`, `failed`, `needs_person` and audio answers
- accept: job `scored` 3 + posted 3 → created; posted 2 → `SuggestionChanged`; job `failed`/`queued` → `NoSuggestion`; job `needs_person` → `NeedsPersonReview`. <!-- Red Team / user decision: needs_person requires override -->
- **decision race:** a 2nd session commits sequence 1; patch `_latest_decision` to return `None` once → identical → `created=False`; different → `ConcurrentDecision`; never two rows per sequence
- **supersede race:** patch `_load_answer` to return the answer as still current while a 2nd session has already superseded it → `AnswerSuperseded`, no decision row stored. <!-- Red Team: check-then-act -->
- **suggestion race:** accept with `_load_answer` returning a stale job state (scored 3) while a 2nd session has retried the job (suggestion cleared) → `SuggestionChanged` or `NoSuggestion`, no row stored
- unrelated `IntegrityError` (e.g. a broken FK, simulated by deleting the answer row in a 2nd session after the load) is **re-raised**, not mapped to `ConcurrentDecision`
- `retry_job`: failed → `queued`, `attempts=0`, `last_error=None`, `changed=True`, returned job reflects DB; queued → `changed=False`; scored / running / needs_person / superseded → `JobNotRetryable`; unknown → `JobNotFound`
- **retry double click:** session X loads the failed job; session Y retries and commits; X's `retry_job` → `changed=False` (not `JobNotRetryable`, not stale). <!-- Red Team: stale identity map -->

### `test_hr_actions_api.py`
- `POST …/override {score:4, reason:"..."}` → 201 `{id, answer_id, kind:"override", score, reason, hr_email, created_at}`; same body again → 200, same `id`
- score 0 / 5 / missing → 422 starting `score:`; reason `"  "` → 422 `reason: must not be blank`; > 2000 chars → 422 `reason: must be at most 2000 characters`
- override sent as `text/plain` or form-encoded → 415 `content type must be application/json`
- superseded answer → 409 `answer has been replaced by a newer submission`; unknown → 404 `answer not found`
- `POST …/accept {score:3}` on scored 3 → 201 `kind:"accept"`, `reason: null`; again → 200; mismatch → 409 `suggested score has changed, reload and try again`; failed job → 409 `no suggested score to accept`; needs_person → 409 `needs a person: use override with a reason`
- `POST /api/hr/jobs/{id}/retry` with `{}` on failed → 200 job view `status:"queued"`; again → 200; scored → 409 `only failed jobs can be retried`; unknown → 404 `job not found`; no body / non-JSON content type → 415
- after override, `GET /api/hr/candidates/{id}` reflects new `final_score` and decisions

## Implementation Steps
1. `route_table.py` + refactor `test_api_doc_coverage.py` to use it → candidate doc tests still green.
2. Fixtures + factories.
3. Write test files in the order above.
4. `cd apps/api && uv run pytest -q`: HR tests fail for expected reasons only; candidate suites green.
5. `make lint` green.

## Success Criteria
- [ ] All files exist and cover every case above
- [ ] HR tests red for expected reasons only; candidate-plan tests green; `make lint` green
- [ ] Every acceptance criterion in `plan.md` maps to at least one test

## Risk Assessment
- Contract wrong during implementation → fix plan + test together, never loosen silently.
- Race tests depend on `_latest_decision`, `_load_answer`; phase 5 must keep those names.
- The route-table and HR doc-coverage tests stay red until phase 5 by design. Phases 3–4 track their own suites.
