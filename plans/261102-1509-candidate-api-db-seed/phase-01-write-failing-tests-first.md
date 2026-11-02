---
phase: 1
title: "Write failing tests first"
status: done
priority: P1
dependencies: []
---

# Phase 1: Write failing tests first

## Overview
Write the full test suite for models, service, API and seed **before any implementation**, against the contracts fixed in phases 2–5. End state: the tests are collected and fail for the expected reason (ImportError / missing route / missing table). That's the "red" step. Phases 2–5 then make them green.

## Requirements
- Tests use only the contracts in this plan: module paths, function signatures, endpoints, status codes and response shapes from phases 2–5. They must not guess at internals beyond that.
- One behaviour per test, with a descriptive name (`test_identical_resubmission_returns_same_receipt`). No plan or phase IDs in test names.
- No mocks of our own code, except the single stale-read hook in the race test (see below). Real SQLite in `tmp_path`.
- After this phase, implementation phases **must not weaken tests**. A test may change only if it is wrong against the plan's contract; say why in the commit message.

## Contracts the tests rely on (defined in later phases)
| Contract | Defined in |
|---|---|
| `app.models`: `Role`, `Question`, `Candidate`, `Answer`, `ScoringJob`; `app.models.enums`: `AnswerKind`, `JobStatus` | Phase 2 |
| `app.services.candidate_access`: `issue_token(db, candidate) -> str`, `find_candidate_by_token(db, raw) -> Candidate \| None` | Phase 3 |
| `app.services.interview_progress.get_progress(db, candidate) -> Progress` | Phase 3 |
| `app.services.answer_submission`: `record_answer(...) -> SubmitResult`, `text_sha256`, `AudioMeta`, exceptions `QuestionNotFound`, `OutOfOrder`, `InterviewClosed`, `ConcurrentSubmission`, private hook `_load_current_answer` | Phase 3 |
| Routes `GET /api/candidate/interview`, `PUT /api/candidate/answers/{qid}`, `PUT /api/candidate/answers/{qid}/audio`; settings injected via `Depends(get_settings)` | Phase 4 |
| `app.seed.data_pack_parser`: `parse_questions_md(path)`, `load_pipeline_people(path)`, `load_pack_answers(dir)`, `DataPackError` | Phase 5 |
| `app.seed.runner.run_seed(session_factory, *, pack_dir, upload_dir, links_path, web_base_url) -> SeedSummary` | Phase 5 |

## Related Code Files
- Modify: `apps/api/tests/conftest.py`: fixtures below
- Create: `apps/api/tests/factories.py`
- Create: `apps/api/tests/test_models.py`
- Create: `apps/api/tests/test_candidate_access.py`
- Create: `apps/api/tests/test_answer_submission.py`
- Create: `apps/api/tests/test_candidate_api.py`
- Create: `apps/api/tests/test_data_pack_parser.py`
- Create: `apps/api/tests/test_seed.py`
- Create: `apps/api/tests/test_api_doc_coverage.py`

## Fixtures (`conftest.py`, `factories.py`)
- `engine(tmp_path)`: file SQLite, `import app.models`, `Base.metadata.create_all`.
- `db_session(engine)`: plain `Session`, for service/model tests.
- `session_factory(engine)`: `sessionmaker` (seed tests; race test's 2nd session).
- `upload_dir(tmp_path)`.
- `client(engine, upload_dir)`: overrides `get_db` and `get_settings` (`UPLOAD_DIR=upload_dir`, `MAX_AUDIO_BYTES=1024`).
- `factories.seed_questions(db)` → 6 synthetic questions Q1–Q6 with rubric `{"1".."4"}`; `make_role(db, title)`; `make_candidate(db, role, id="C0001") -> (candidate, raw_token)` (uses `issue_token`); `answer_all(db, candidate)` helper.
- `PACK_DIR` constant → repo `business-systems-pack/` (resolved from `tests/` path).

Note: `import app.models` in conftest makes the **whole** suite red, including `test_health`, until phase 2. That's expected.

## Test cases

### `test_models.py`
- two current answers for the same (candidate, question) → `IntegrityError`
- a superseded answer plus a current one for the same pair → allowed
- second `ScoringJob` for the same answer → `IntegrityError`
- invalid `kind` / invalid job `status` → `IntegrityError` (CHECK)
- `kind=text` with `text=None` → `IntegrityError`
### `test_candidate_access.py`
- `issue_token` returns a raw token; the DB stores only its sha256 (raw token not in the row)
- `find_candidate_by_token(raw)` → that candidate; unknown → None
- re-issue → old token → None, new token → candidate

### `test_answer_submission.py`
- first submit → `created=True`; 1 answer, 1 job `queued`
- identical replay → `created=False`, same answer id; still 1 answer, 1 job
- different content on an answered question → new current answer; old has `superseded_at`; old job `superseded`; new job `queued`
- question that isn't current and isn't answered → `OutOfOrder`
- replacing an already-answered question while incomplete → allowed
- all 6 answered → different content raises `InterviewClosed`; identical replay still `created=False`
- unknown question id → `QuestionNotFound`
- `enforce_rules=False` with explicit `answer_id` / `submitted_at` → stored as given, gaps allowed
- **race:** a 2nd session commits a current answer for the same pair; monkeypatch `_load_current_answer` to return `None` once (stale read) → same content gives `created=False` replay, different content raises `ConcurrentSubmission`; there is never more than one current row
- `get_progress`: fresh → current Q1; answer Q1 → Q2; answer Q3 out of band (`enforce_rules=False`) → current is still Q2, `answered_count=2`

### `test_candidate_api.py`
Every error test asserts the status code **and** the exact `detail` string from phase 4's "Fixed error `detail` strings" table, and that `detail` is a `str`.
- no header / malformed header / unknown token / rotated-out token → 401 `invalid or missing candidate token`, on all 3 endpoints
- PUT text with no body → 422 with a string `detail` (the custom handler, not FastAPI's list)
- GET fresh → `current_question.id == "Q1"`, `answered_count == 0`, `completed is False`
- answer Q1 then GET → current Q2; GET again (reload) → same body
- PUT text → 201 receipt `{answer_id, question_id, kind:"text", received_at, status:"received"}`; same PUT again → 200, same `answer_id`; DB has 1 answer + 1 job
- PUT different text on Q1 → 201 with a new `answer_id`; GET still lists Q1 once
- PUT Q3 while current is Q1 → 409; `Q9` → 404; `"   "` → 422; > 10 000 chars → 422
- all answered → replace → 409
- audio `.m4a` small bytes → 201, `kind:"audio"`, file exists under `upload_dir`; same bytes again → 200, no second file
- audio `.txt` / `text/plain` → 415; over 1024 bytes → 413 and no file left in `upload_dir`; empty file → 422
- **leak test:** recursively walk every candidate response body (GET + both PUTs) and assert none of the keys `score`, `rubric`, `reason`, `job`, `jobs`, `email`, `candidate_id` appear, and that `status` appears only as `"received"`
- two candidates: A's token never returns B's answers or name

### `test_api_doc_coverage.py`
Keeps `docs/api-doc.md` honest without parsing prose:
- for every `APIRoute` in `create_app().routes` under `/api`, the doc contains a heading `### <METHOD> <path>` (path template as written, e.g. `{question_id}`)
- each candidate endpoint section (text between its heading and the next `### `) mentions every status code in its expected set: GET `{200, 401}`; PUT text `{201, 200, 401, 404, 409, 422}`; PUT audio `{201, 200, 401, 404, 409, 413, 415, 422}`
- each of those sections contains `**Auth:**`, `**Request:**`, `**Errors:**`, and a fenced `json` block

### `test_data_pack_parser.py`
- real `questions.md` → 6 questions Q1–Q6 in order, each with rubric keys `"1"`–`"4"`; 5 roles
- tmp questions.md missing a rubric level → `DataPackError`
- real answers dir → 35 answers, 5 audio (`A031`–`A035`) with an existing audio path
- answer whose `candidate_id` isn't in the pipeline log → `DataPackError` (tmp fixture)

### `test_seed.py` (real pack, tmp DB / upload dir / links path)
- first run: 5 roles, 6 questions, 18 candidates, 35 answers (34 current), A022 superseded, A023 current, jobs 34 `queued` + 1 `superseded`, 5 audio files in `upload_dir`
- links CSV: 18 rows, `link` starts with `web_base_url + "/i/"`, each token resolves to its candidate
- second run: same counts (no duplicates), every token changed, first-run tokens → `find_candidate_by_token` returns None
- pack files unchanged after seeding (mtime/size check on `questions.md` and one answer)

## Implementation Steps
1. Fixtures + factories.
2. Write each test file in the order above.
3. `cd apps/api && uv run pytest -q`: confirm every test **fails** (collection ImportError is fine), and none fails because of a typo in the test itself.
4. `make lint` passes (ruff runs on `tests/`). Only lint must be green; tests are expected red.

## Success Criteria
- [ ] All 7 test files exist and cover every case above
- [ ] `pytest` red for the expected reasons only; `make lint` green
- [ ] Every acceptance criterion in `plan.md` maps to at least one test

## Risk Assessment
- Tests written against contracts that turn out wrong → fix the contract in the plan and the test together. Never silently loosen an assertion.
- The race test depends on the private hook name `_load_current_answer`; phase 3 must keep that name.
