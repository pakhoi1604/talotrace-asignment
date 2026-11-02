---
phase: 2
title: "Data model + migration"
status: done
priority: P1
dependencies: [1]
---

# Phase 2: Data model + migration

## Overview
Add the SQLAlchemy models the candidate flow and the later worker/HR plans need: `roles`, `questions`, `candidates`, `answers`, `scoring_jobs`. Generate the first migration with autogenerate.

## Requirements
- Functional: schema enforces the rules itself: one current answer per (candidate, question), one job per answer, valid kinds and statuses.
- Non-functional: named constraints (SQLite batch mode needs names); autogenerate only (AGENTS.md rule 1); `alembic check` clean.

## Architecture

```
roles 1─* candidates 1─* answers *─1 questions
                              1─1 scoring_jobs
```

| Table | Columns | Constraints |
|---|---|---|
| `roles` | `id` int PK, `title` str(100) | UNIQUE(title) |
| `questions` | `id` str(4) PK ("Q1"), `position` int, `text` Text, `rubric` JSON (`{"1": "...", ..., "4": "..."}`) | UNIQUE(position) |
| `candidates` | `id` str(16) PK (pack `candidate_id`, e.g. "C2041"), `name`, `email`, `role_id` FK, `access_token_hash` str(64) null, `token_issued_at` dt null, `created_at` | UNIQUE(access_token_hash), INDEX(role_id) |
| `answers` | `id` str(36) PK (pack `answer_id` or uuid4), `candidate_id` FK, `question_id` FK, `kind` str(10), `text` Text null, `audio_path` str null, `audio_content_type` str null, `audio_size_bytes` int null, `content_sha256` str(64), `submitted_at` dt, `superseded_at` dt null | CHECK kind IN ('text','audio'); CHECK (kind='text' AND text IS NOT NULL AND audio_path IS NULL) OR (kind='audio' AND audio_path IS NOT NULL); **partial UNIQUE(candidate_id, question_id) WHERE superseded_at IS NULL** |
| `scoring_jobs` | `id` int PK, `answer_id` FK, `status` str(20) default 'queued', `attempts` int default 0, `last_error` Text null, `created_at`, `updated_at` | UNIQUE(answer_id); CHECK status IN ('queued','running','scored','failed','needs_person','superseded') |

Notes:
- Candidate ↔ interview merged into `candidates`: each pack candidate has exactly one role, one link. A separate `interviews` table isn't needed yet.
- Job statuses fixed now (including `running` for the worker, `superseded` for latest-wins) so SQLite doesn't need a CHECK-change migration later. Brief's 4 HR-visible statuses ⊂ this set.
- Statuses and kinds are `StrEnum`s in Python and are stored as strings with a CHECK constraint, not a native enum.
- All datetimes UTC (`DateTime(timezone=True)`), helper `utcnow()`.
- The partial unique index gives "only one current answer". Old versions stay for HR history.
## Related Code Files
- Modify: `apps/api/app/db/base.py`: add `MetaData(naming_convention=...)` (ix/uq/ck/fk/pk)
- Create: `apps/api/app/models/__init__.py` (re-export all models so Alembic sees them)
- Create: `apps/api/app/models/enums.py`: `AnswerKind`, `JobStatus` StrEnums
- Create: `apps/api/app/models/role.py`, `question.py`, `candidate.py`, `answer.py`, `scoring_job.py`
- Create: `apps/api/app/core/time.py`: `utcnow()`
- Modify: `apps/api/migrations/env.py`: `import app.models  # noqa: F401` so metadata is populated
- Create (generated): `apps/api/migrations/versions/<rev>_candidate_answer_job_tables.py`
- Tests already exist from phase 1 (`tests/test_models.py`, conftest `create_all`). Do not edit them except to fix a contract bug.

## Implementation Steps
1. Naming convention on `Base.metadata`.
2. Write models (SQLAlchemy 2.0 `Mapped[...]` style). Partial index:
   ```python
   Index("uq_answers_current", "candidate_id", "question_id",
         unique=True, sqlite_where=text("superseded_at IS NULL"))
   ```
3. Import models in `migrations/env.py`.
4. `make migration m="candidate answer job tables"` → **read the generated file**: confirm all CHECKs, the unique on `scoring_jobs.answer_id`, and that `sqlite_where` is rendered on `uq_answers_current`.
   - If autogenerate drops `sqlite_where`: switch to the autogenerate-friendly pattern instead of hand-editing the migration: `is_current` Boolean **nullable** (True = current, NULL = superseded) + `UniqueConstraint(candidate_id, question_id, is_current)` (SQLite treats NULLs as distinct). Regenerate.
5. `make migrate`, then `cd apps/api && uv run alembic check`.
6. `uv run pytest tests/test_models.py tests/test_health.py` → green.

## Success Criteria
- [ ] Migration generated (not hand-written), applies cleanly on empty DB
- [ ] `alembic check` reports no drift
- [ ] `tests/test_models.py` and `tests/test_health.py` green (other suites may still be red)
- [ ] `make lint` green

## Risk Assessment
- Alembic may not render `sqlite_where` → fallback pattern in step 4.
- Adding a naming convention after tables exist would cause drift; safe here because this is the first model migration.
