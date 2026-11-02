---
phase: 4
title: "HR read endpoints"
status: done
priority: P1
dependencies: [3]
---

# Phase 4: HR read endpoints

## Overview
Roles, candidates per role, full candidate review, jobs list, audio playback. All read-only and behind `get_current_hr`. Done = `test_hr_read_api.py` green (route-table permission test goes green in phase 5 once all 9 guarded routes exist).

## Requirements
- Functional: everything HR needs to review: answers, which submission counts, job status, suggested score + reason, decisions (including on replaced answers), final score; status of every job; audio arrival + playback.
- Non-functional: no N+1 (`selectinload`); audio confined to the resolved `UPLOAD_DIR` and served with a server-chosen content type; every timestamp carries a UTC offset; a non-`scored`/`needs_person` job never exposes a score, even if the DB holds one.

## Architecture

### `app/services/hr_review.py` (query + assembly, no FastAPI)
```python
def visible_suggestion(job) -> tuple[int | None, str | None]
    # (suggested_score, suggested_reason) only if job.status in (scored, needs_person); else (None, None)
def final_score(answer) -> tuple[int | None, Literal["hr","suggested"] | None]
    # newest decision → (score,"hr"); job.status == scored and visible score → (score,"suggested"); else (None, None)
def list_roles(db) -> list[RoleSummary]
def list_role_candidates(db, role_id) -> RoleCandidates | None
def get_candidate_review(db, candidate_id) -> CandidateReview | None
def list_jobs(db, status: JobStatus | None) -> JobList
```
Rules:
- **Read-side gate:** every response and aggregate goes through `visible_suggestion`. The ORM invariant (phase 2) stops bad writes made through the ORM. This gate stops bad rows written by raw SQL, bulk updates or a buggy worker from ever showing a failed job as a score. <!-- Red Team: read-side gating -->
- "Current" = answers with `superseded_at IS NULL`. `job_counts` uses current answers' jobs only, keys `queued, running, scored, failed, needs_person` (always present, 0 default).
- `avg_suggested` = mean visible `suggested_score` over current answers whose job is **`scored` only**. `needs_person` scores are excluded because the model didn't trust them. Round to 2 dp; `null` if none. <!-- Red Team: avg contradiction -->
- `avg_final` = mean of `final_score` over current answers that have one; `null` if none.
- `last_activity_at` = max(`submitted_at`) over all the candidate's answers (computed in SQL or after attaching UTC; never mix naive/aware in Python); `null` if none.
- Jobs list: default `status IN (queued, running, scored, failed, needs_person)`; explicit `status` filters exactly (incl. `superseded`). Order `updated_at desc, id desc`. `counts` always covers all 6 statuses across all jobs.

### Routes (`app/api/routes/hr_review.py`, router-level `require_json_content_type` + `get_current_hr`)
| Method | Path | 200 body | Errors |
|---|---|---|---|
| GET | `/api/hr/roles` | `{roles: [{id, title, candidate_count, job_counts}]}` sorted by title | 401 |
| GET | `/api/hr/roles/{role_id}/candidates` | `{role: {id,title}, total_questions, candidates: [{id, name, answered_count, total_questions, avg_suggested, avg_final, job_counts, last_activity_at}]}` sorted by name | 401, 404 `role not found` |
| GET | `/api/hr/candidates/{candidate_id}` | `CandidateReview` (below) | 401, 404 `candidate not found` |
| GET | `/api/hr/jobs?status=` | `{counts: {...6}, jobs: [JobListItem]}` | 401, 422 `status: ...` |
| GET | `/api/hr/answers/{answer_id}/audio` | raw bytes (200, or 206 for a `Range` request) | 401, 404 `audio not found`, 416 bad range |

`CandidateReview`:
```json
{
  "id": "C2041", "name": "…", "email": "…",
  "role": { "id": 1, "title": "Backend Engineer" },
  "total_questions": 6, "answered_count": 6,
  "avg_suggested": 3.25, "avg_final": 3.4,
  "job_counts": { "queued": 0, "running": 0, "scored": 4, "failed": 1, "needs_person": 1 },
  "questions": [{
    "question": { "id": "Q1", "position": 1, "text": "…", "rubric": { "1": "…", "2": "…", "3": "…", "4": "…" } },
    "answer": {
      "id": "A001", "kind": "text", "text": "…", "audio": null,
      "submitted_at": "2026-09-14T09:41:00Z", "submission_count": 1,
      "job": { "id": 12, "status": "scored", "attempts": 1, "last_error": null,
               "suggested_score": 3, "suggested_reason": "…", "needs_person_reason": null,
               "model": "gemini-…", "updated_at": "2026-09-14T09:42:10Z" },
      "final_score": 3, "final_source": "suggested",
      "decisions": [],
      "earlier_submissions": []
    }
  }]
}
```
- `answer` is `null` for unanswered questions.
- `audio` = `{content_type, size_bytes, url}`, where `url = "/api/hr/answers/{id}/audio"` and `content_type` comes from the extension map below (not the stored upload header).
- `earlier_submissions[]` = superseded versions, newest first: `{id, kind, text, audio, submitted_at, superseded_at, decisions}`. No job/score: they don't count. `decisions` keeps HR's reasons visible after a candidate replaces an answer. A resubmission starts a fresh final score. <!-- Red Team: orphaned decisions -->
- `decisions[]` newest first: `{id, kind, score, reason, hr_email, created_at}`.
- `JobListItem` = `{id, status, attempts, last_error, needs_person_reason, updated_at, answer: {id, kind, question_id}, candidate: {id, name}, role: {id, title}}`. No score fields.
- **All datetime fields use `UtcDatetime`** (phase 3), so the JSON always has `Z`/`+00:00`. The same type is applied to the candidate schemas (`received_at`), because `docs/api-doc.md` already promises `Z` there and SQLite returns naive values. One-line change per field. Candidate tests must stay green. <!-- Red Team: naive datetimes -->

### Audio route (hardened) <!-- Red Team: stored XSS -->
1. Load answer; not found / `kind != audio` → 404.
2. `base = resolve_api_path(settings.UPLOAD_DIR).resolve()` (same helper as the candidate upload route); `path = (base / answer.audio_path).resolve()`; require `path.is_relative_to(base)` and `path.is_file()`, else 404.
3. Content type from a fixed map on `path.suffix.lower()`: `.m4a`/`.mp4` → `audio/mp4`, `.mp3` → `audio/mpeg`, `.wav` → `audio/wav`, `.webm` → `audio/webm`, `.ogg` → `audio/ogg`; unmapped → 404. **Never echo `answer.audio_content_type`.** The candidate controls it (upload check is only `startswith("audio/")`), and values like `audio/x, text/html` would render as HTML on the HR origin.
4. `FileResponse(path, media_type=mapped, headers={"X-Content-Type-Options": "nosniff", "Content-Security-Policy": "sandbox; default-src 'none'", "Content-Disposition": "inline"})`. Starlette serves `Range` requests as 206 and bad ranges as 416.

`status` query param typed `JobStatus | None` → the custom 422 handler gives `status: Input should be …`.

### `docs/api-doc.md` + `api-types.ts`
5 sections with the full checklist. The doc states:
- job statuses `queued/running/scored/failed/needs_person/superseded`; the UI shows `running` as "queued" (the brief's four statuses)
- `suggested_score` is only present for `scored`/`needs_person`, and `failed` never carries a score
- `avg_suggested` counts `scored` only
- `final_source` meaning
- which submission counts; decisions on earlier submissions
- audio: content type from extension, `nosniff`, 206/416 and `Accept-Ranges` behaviour; 416 body is Starlette's, not `{detail}`

Types: `RoleSummary`, `JobCounts`, `RoleCandidates`, `CandidateRow`, `CandidateReview`, `QuestionReview`, `AnswerReview`, `JobView`, `DecisionView`, `EarlierSubmission`, `JobList`, `JobListItem`, `JobStatus`.

## Related Code Files
- Create: `apps/api/app/services/hr_review.py`
- Create: `apps/api/app/api/routes/hr_review.py`
- Modify: `apps/api/app/schemas/hr.py`: read DTOs (all datetimes `UtcDatetime`)
- Modify: `apps/api/app/schemas/candidate.py`: datetime fields → `UtcDatetime`
- Modify: `apps/api/app/main.py`: include router
- Modify: `docs/api-doc.md`, `apps/web/src/lib/api-types.ts`

## Implementation Steps
1. `visible_suggestion`, `final_score`, aggregation helpers.
2. Schemas + routes + wiring → `test_hr_read_api.py` green.
3. `UtcDatetime` on candidate schemas → candidate suites still green.
4. Docs + types; check `detail` strings against real responses. `make lint`.

## Success Criteria
- [ ] `test_hr_read_api.py` green with no test edits (incl. ORM-bypass, hostile content type, relative `UPLOAD_DIR`, Range, decision-survives-resubmission)
- [ ] Candidate suites still green after the `UtcDatetime` change
- [ ] Docs + types updated; `make lint` green

## Risk Assessment
- Lazy-load explosion → `selectinload(Candidate.answers).selectinload(Answer.job)` and `.selectinload(Answer.decisions)`.
- `email` exposed to HR only. HR schemas live in a separate module and are never used on candidate routes; the candidate leak test guards keys.
- Seeded data has no scores until the worker plan lands, so all jobs show `queued`. Tests use `set_job_result`.
- Upload validation still stores a loose content type. Harmless now (HR route ignores it). Tightening the candidate allow-list is a follow-up for the candidate area, out of scope here.
