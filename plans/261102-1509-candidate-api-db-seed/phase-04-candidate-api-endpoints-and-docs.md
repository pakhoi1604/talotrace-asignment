---
phase: 4
title: "Candidate API endpoints + contract docs"
status: done
priority: P1
dependencies: [3]
---

# Phase 4: Candidate API endpoints + contract docs

## Overview
Expose three candidate endpoints behind token auth, with response models that cannot carry grades. Update the API contract doc and the FE type mirror in the same change (AGENTS.md rule 2). Done = `tests/test_candidate_api.py` from phase 1 is green.

## Requirements
- Functional: resume at the current question; instant receipt; text + audio; correct status codes.
- Non-functional: permissions enforced server-side only; audio size capped while streaming; no raw token in logs.

## Architecture

**Auth dependency** `get_current_candidate` (`app/api/deps.py`): reads `Authorization: Bearer <token>` → `find_candidate_by_token` → 401 `{"detail": "invalid or missing candidate token"}` for every failure, using the same message each time so tokens can't be probed. The candidate ID never appears in a path, so a candidate cannot address another candidate.

| Method | Path | Success | Errors |
|---|---|---|---|
| GET | `/api/candidate/interview` | 200 `InterviewView` | 401 |
| PUT | `/api/candidate/answers/{question_id}` body `{"text": str}` | 201 new / 200 identical replay → `AnswerReceipt` | 401, 404 unknown question, 409 out of order / interview closed / concurrent, 422 empty or > 10 000 chars |
| PUT | `/api/candidate/answers/{question_id}/audio` multipart `file` | 201 / 200 → `AnswerReceipt` | 401, 404, 409, 413 > `MAX_AUDIO_BYTES` (25 MB), 415 type not allowed, 422 empty file |

Response models (`app/schemas/candidate.py`). These are the **only** shapes candidate routes may return:
```python
class CurrentQuestion(BaseModel): id: str; position: int; text: str
class AnsweredItem(BaseModel):   question_id: str; position: int; kind: Literal["text","audio"]; received_at: datetime
class InterviewView(BaseModel):
    candidate_name: str; role: str; total_questions: int; answered_count: int
    completed: bool; current_question: CurrentQuestion | None; answered: list[AnsweredItem]
class AnswerReceipt(BaseModel):
    answer_id: str; question_id: str; kind: Literal["text","audio"]
    received_at: datetime; status: Literal["received"]
```
No rubric, score, job status, email or other candidates. `received_at` = `submitted_at` of the current answer.

**Audio route flow:**
1. Allow-list: ext ∈ {.m4a, .mp3, .wav, .webm, .ogg, .mp4} and content-type starts with `audio/` (or `video/mp4`/`video/webm` for browser recorders) → else 415.
2. Stream the upload in chunks to `UPLOAD_DIR/tmp-<uuid>`, hashing (`sha256(b"audio:" + bytes)`) and counting as it goes; abort + delete when the cap is exceeded → 413; zero bytes → 422.
3. The route generates `answer_id = uuid4()` itself and renames the temp file to `UPLOAD_DIR/<answer_id><ext>`, then calls `record_answer(kind=audio, answer_id=answer_id, audio=AudioMeta(...))`. If the result is a replay (`created=False`) or any exception is raised, delete that file. Result: a file exists only for a committed answer, apart from a process crash mid-call.
4. `audio_path` is stored relative to `UPLOAD_DIR`.

**Error mapping:** domain exceptions → `HTTPException` in a small helper in the router (`QuestionNotFound`→404, `OutOfOrder`/`InterviewClosed`/`ConcurrentSubmission`→409). The `detail` strings are fixed in the table below; tests assert them exactly.

**422 shape:** FastAPI's default 422 body is `{"detail": [ {...} ]}`, which breaks the documented `{ "detail": string }` error shape. Add a `RequestValidationError` handler in `main.py` that returns `{"detail": "<field>: <message>"}` (first error, field = last `loc` item). This applies to every endpoint.

### Fixed error `detail` strings
| Code | When | `detail` |
|---|---|---|
| 401 | header missing / malformed / unknown or rotated token | `invalid or missing candidate token` |
| 404 | `question_id` not in Q1–Q6 | `question not found` |
| 409 | unanswered question that is not the current one | `answer the current question first` |
| 409 | all questions answered, different content sent | `interview is closed` |
| 409 | concurrent different submission for the same question | `another submission for this question is in progress, please retry` |
| 413 | audio bigger than `MAX_AUDIO_BYTES` | `audio file too large (max 25 MB)` (size taken from settings) |
| 415 | extension or content type not allowed | `unsupported audio type` |
| 422 | text blank after trim | `text: must not be blank` |
| 422 | text > 10 000 chars | `text: must be at most 10000 characters` |
| 422 | body / `file` field missing | `<field>: Field required` (from handler) |
| 422 | audio upload has 0 bytes | `audio file is empty` |

### `docs/api-doc.md` content (required)
Every endpoint section follows the existing `GET /api/health` format and **must** contain all of:
1. `### METHOD /path` heading + one-line purpose
2. **Auth:** which credential, plus the header example `Authorization: Bearer <token>`
3. **Request:** path params, headers, body: a field table (name, type, required, rules) + a JSON or multipart example
4. **Response <code>:** one block **per success code** (201 *and* 200 for the PUTs, saying when each happens), each with a JSON example + a field table (field, type, description)
5. **Errors:** a table with **every** status code the endpoint can return (code | when | exact `detail`), copied from the table above
6. Behaviour notes: idempotent replay, latest-wins replace, order rule, interview closed

Also update the doc header:
- **Auth model:** candidate token = a personal reusable link token (`/i/<token>` in the web app, sent as `Authorization: Bearer`); stored hashed; rotated by `make seed`.
- **Error shape:** `{ "detail": string }` applies to all codes, 422 included.

Drafts to put in the doc (shortened here; the doc carries the full field tables):

`GET /api/candidate/interview` → **200**
```json
{
  "candidate_name": "Minh Anh Tran",
  "role": "Backend Engineer",
  "total_questions": 6,
  "answered_count": 1,
  "completed": false,
  "current_question": { "id": "Q2", "position": 2, "text": "Describe a time you had to meet a tight deadline. What did you do?" },
  "answered": [ { "question_id": "Q1", "position": 1, "kind": "text", "received_at": "2026-11-02T08:15:00Z" } ]
}
```
`current_question` is `null` when `completed` is `true`. Errors: 401.

`PUT /api/candidate/answers/{question_id}` with body `{ "text": "..." }` → **201** (new or replaced answer) / **200** (identical to current answer; nothing changed)
```json
{ "answer_id": "6f1c2a9e-...", "question_id": "Q2", "kind": "text", "received_at": "2026-11-02T08:20:11Z", "status": "received" }
```
Errors: 401, 404, 409 (×3), 422 (blank, too long, missing field).

`PUT /api/candidate/answers/{question_id}/audio`, `multipart/form-data` field `file` (.m4a .mp3 .wav .webm .ogg .mp4, ≤ 25 MB) → **201** / **200**, same receipt with `"kind": "audio"`. Errors: 401, 404, 409 (×3), 413, 415, 422 (missing file, empty file).

## Related Code Files
- Create: `apps/api/app/api/deps.py`: `get_current_candidate`
- Create: `apps/api/app/schemas/__init__.py`, `apps/api/app/schemas/candidate.py`
- Create: `apps/api/app/api/routes/candidate.py`
- Create: `apps/api/app/services/audio_storage.py`: streaming save with cap + hash, delete helper
- Modify: `apps/api/app/main.py`: include candidate router under `/api`; `RequestValidationError` handler → `{"detail": "<field>: <message>"}`
- Modify: `apps/api/app/core/config.py`: `MAX_AUDIO_BYTES: int = 25 * 1024 * 1024`. Routes read settings via `Depends(get_settings)` (tests override it)
- Modify: `docs/api-doc.md`: header (auth model, error shape incl. 422) + 3 endpoint sections meeting the 6-item checklist above
- Modify: `apps/web/src/lib/api-types.ts`: `InterviewView`, `CurrentQuestion`, `AnsweredItem`, `AnswerReceipt`
- Modify: `docs/architecture.md`: Data model section; answer lifecycle (submit → answer + queued job in one tx; latest-wins; worker must re-check `running` + current before writing a score)
- Tests already exist from phase 1: `tests/test_candidate_api.py`, `tests/test_api_doc_coverage.py`.

## Implementation Steps
1. Schemas, deps, audio storage helper, 422 handler.
2. Router with the 3 endpoints. Return 201 vs 200 via `Response.status_code` based on `created`.
3. Wire into `main.py`.
4. `uv run pytest tests/test_candidate_api.py` → green, with no test edits.
5. Write the `docs/api-doc.md` sections per the checklist. Copy the `detail` strings from the table, and check them against real responses (run the app and curl each error case once, or read the test assertions). `test_api_doc_coverage.py` → green.
6. Update `api-types.ts`: add an `AnswerReceipt.status: "received"` literal and keep `ApiError` as is. `make lint`.

## Success Criteria
- [ ] `test_candidate_api.py` green, including the leak test and exact `detail` assertions
- [ ] `test_api_doc_coverage.py` green: every route has a doc section, and every status code it returns is listed
- [ ] Each endpoint section in `docs/api-doc.md` has: Auth, Request (field table + example), one Response block per success code (JSON example + field table), Errors table (code / when / exact `detail`)
- [ ] `api-types.ts` mirrors the doc
- [ ] `docs/architecture.md` data model + lifecycle filled in
- [ ] `make lint` green; all suites except `test_seed.py` / `test_data_pack_parser.py` green

## Risk Assessment
- Content-type spoofing: the allow-list is a basic check, not real validation. Acceptable because files are only stored and served to HR, never executed. Magic-byte sniffing is out of scope.
- Orphan files if the process dies between save and commit: low impact; note it in architecture "not built".
- A token in the URL path on the frontend (`/i/<token>`) can leak via Referer. Add `Referrer-Policy: no-referrer` when the FE plan builds that page (note in FE plan).
