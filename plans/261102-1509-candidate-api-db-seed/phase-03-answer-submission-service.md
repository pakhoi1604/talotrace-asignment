---
phase: 3
title: "Answer submission service"
status: done
priority: P1
dependencies: [2]
---

# Phase 3: Answer submission service

## Overview
One domain module holding the business rules for tokens, progress and recording an answer. The API (phase 4) and the seed (phase 5) both call it, so the rules live in one place. Done = the phase 1 service tests pass.

## Requirements
- Functional: token issue/lookup; current-question computation; `record_answer` with idempotent replay, latest-wins supersede, order rule, closed-interview rule, job enqueue in the same transaction; safe under double-click races.
- Non-functional: no FastAPI imports (pure domain + SQLAlchemy); raises domain exceptions that routes map to HTTP codes.

## Architecture

### `app/services/candidate_access.py`
```python
def issue_token(db, candidate) -> str          # token_urlsafe(32); stores sha256; sets token_issued_at; returns raw token
def find_candidate_by_token(db, raw) -> Candidate | None   # lookup by sha256(raw)
```

### `app/services/interview_progress.py`
```python
@dataclass
class Progress:
    total: int; answered: list[Answer]; current_question: Question | None; completed: bool
def get_progress(db, candidate) -> Progress
# current_question = lowest-position question with no current answer; completed = none left
```

### `app/services/answer_submission.py`
```python
class QuestionNotFound(Exception); class OutOfOrder(Exception)
class InterviewClosed(Exception); class ConcurrentSubmission(Exception)

@dataclass
class SubmitResult: answer: Answer; created: bool

def text_sha256(text: str) -> str   # sha256(b"text:" + stripped utf-8)
def record_answer(db, candidate, question_id, *, kind, content_sha256,
                  text=None, audio=None,            # audio = AudioMeta(path, content_type, size)
                  answer_id=None, submitted_at=None, enforce_rules=True) -> SubmitResult
```

`record_answer` flow (one transaction, the service commits):
1. Question missing → `QuestionNotFound`.
2. Load current answer via `_load_current_answer(db, candidate_id, question_id)` (candidate, question, `superseded_at IS NULL`). Keep this helper name: the phase 1 race test patches it.
3. `current.content_sha256 == content_sha256` → return `SubmitResult(current, created=False)` (idempotent replay, nothing written).
4. If `enforce_rules`:
   - progress completed → `InterviewClosed`
   - no current answer and question ≠ `current_question` → `OutOfOrder`
5. If current exists: `current.superseded_at = now`; its job `status = superseded`, `updated_at = now` (whatever status it had; worker plan must re-check before writing a score).
6. Insert new `Answer` (id = `answer_id or uuid4`, `submitted_at or now`) + `ScoringJob(status=queued)`; commit.
7. `IntegrityError` (concurrent insert hit the partial unique index) → rollback, reload current: same hash → `SubmitResult(current, False)`; else → `ConcurrentSubmission` (route → 409 "please retry").

`enforce_rules=False` is used only by the seed (pack data has gaps and was submitted before rules existed). Replay and supersede still apply, so the seed gives A022 → superseded, A023 → current.

## Related Code Files
- Create: `apps/api/app/services/__init__.py`
- Create: `apps/api/app/services/candidate_access.py`
- Create: `apps/api/app/services/interview_progress.py`
- Create: `apps/api/app/services/answer_submission.py`
- Tests already exist from phase 1: `tests/test_candidate_access.py`, `tests/test_answer_submission.py`, `tests/factories.py`.

## Implementation Steps
1. `candidate_access` (sha256 via `hashlib`, never log raw token).
2. `interview_progress`.
3. `answer_submission` per the flow above. Audio file handling stays in the route (phase 4); the service only receives metadata + hash.
4. `uv run pytest tests/test_candidate_access.py tests/test_answer_submission.py` → green, with no test edits.

## Success Criteria
- [ ] `test_candidate_access.py` + `test_answer_submission.py` green (including the race test)
- [ ] No path creates two current answers or two jobs for one answer
- [ ] `make lint` green

## Risk Assessment
- SQLite deferred transactions: two writers can both read "no current". The partial unique index + step 7 handle this; test it explicitly.
- Superseding a `running` job: the worker plan must write a score only if the job is still `running` and the answer is still current. Record this contract in `docs/architecture.md` (phase 4).
