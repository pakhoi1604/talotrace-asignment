# API Documentation

**Base URL:** `/api` (via Next.js rewrite — use this from browser code). Direct: `http://localhost:8000/api` (server-side fetches, scripts, curl).

**Auth model:**
- `candidate token` — a personal, reusable link token. The web app serves it at `/i/<token>`; clients send it as `Authorization: Bearer <token>`. Stored hashed (sha256) in the database; rotated by `make seed` (old links stop working).
- `hr_session` cookie — **MOCK sign-in**, one account from `HR_EMAIL`/`HR_PASSWORD` in `apps/api/.env`. httpOnly, SameSite=Lax. Sessions end on sign-out, after `HR_SESSION_TTL_HOURS`, or when the `.env` account changes. HR routes read only this cookie; a candidate Bearer token is never accepted on `/api/hr/*`. HR `POST` routes require `Content-Type: application/json` (415 otherwise).

**Frontend notes (HR):** browser calls go through `/api/*` and send the cookie automatically. Server components calling `API_URL` must forward the incoming `cookie` header and render dynamically (no caching across sessions). `DELETE /api/hr/session` returns **204 with an empty body** — don't parse JSON.

**Error shape:** `{ "detail": string }` — applies to every status code, 422 included. Validation errors report the first problem as `"<field>: <message>"`.

**Change rule:** this file is the single source of truth. Any endpoint change (path, method, auth, request, response, error) updates this doc in the same change. The frontend learns endpoints and shapes only from this file; `apps/web/src/lib/api-types.ts` mirrors it.

---

### GET /api/health

Liveness + database connectivity check.

**Auth:** none

**Request:** no parameters, no body.

**Response 200**

```json
{ "status": "ok", "db": "ok" }
```

| Field | Type | Description |
|---|---|---|
| `status` | string | `"ok"` when the app is running |
| `db` | string | `"ok"` when `SELECT 1` succeeds against the database |

**Errors:** `503` — database unreachable, `{ "detail": "db unavailable" }`

---

### GET /api/candidate/interview

The candidate's interview view: who they are, how far along they are, and the question to answer next. Reload-safe — resume where they left off.

**Auth:** candidate token — `Authorization: Bearer <token>`

**Request:** no parameters, no body.

**Response 200**

```json
{
  "candidate_name": "Nhi Van Tran",
  "role": "Backend Engineer",
  "total_questions": 6,
  "answered_count": 1,
  "completed": false,
  "current_question": {
    "id": "Q2",
    "position": 2,
    "text": "Describe a time you had to meet a tight deadline. What did you do?"
  },
  "answered": [
    {
      "question_id": "Q1",
      "position": 1,
      "kind": "text",
      "received_at": "2026-11-02T08:15:00Z"
    }
  ]
}
```

| Field | Type | Description |
|---|---|---|
| `candidate_name` | string | Candidate's display name |
| `role` | string | Role title the candidate applied for |
| `total_questions` | number | Number of interview questions |
| `answered_count` | number | Questions with a current (latest) answer |
| `completed` | boolean | `true` when every question has a current answer; `current_question` is then `null` |
| `current_question` | object \| null | Lowest-position unanswered question |
| `current_question.id` | string | Question id, e.g. `"Q2"` |
| `current_question.position` | number | 1-based position |
| `current_question.text` | string | Question text |
| `answered` | array | Current answers, ordered by question position |
| `answered[].question_id` | string | Question id |
| `answered[].position` | number | 1-based position |
| `answered[].kind` | string | `"text"` or `"audio"` |
| `answered[].received_at` | string (datetime) | When the current answer was submitted |

**Errors:**

| Code | When | `detail` |
|---|---|---|
| 401 | Header missing / malformed / unknown or rotated token | `invalid or missing candidate token` |

---

### PUT /api/candidate/answers/{question_id}

Submit or replace a typed answer. Returns `201` when an answer was created or replaced, `200` when the body is identical to the current answer (idempotent replay — nothing changes).

Rules: only the **current** (lowest-position unanswered) question or an **already-answered** question may be submitted. Different content on an answered question creates a new version — the old answer and its scoring job are marked superseded (latest wins). Once every question has a current answer the interview is **closed** and new content is rejected; identical replays still return `200`.

**Auth:** candidate token — `Authorization: Bearer <token>`

**Request:**

| Field | Type | Required | Rules |
|---|---|---|---|
| `question_id` | path param | yes | An existing question id, e.g. `Q2` |
| `text` | string (JSON body) | yes | Non-blank after trim, ≤ 10 000 characters |

```json
{ "text": "At my last company we had a payments service..." }
```

**Response 201** (new or replaced answer) / **200** (identical replay)

```json
{
  "answer_id": "6f1c2a9e-3b7d-4c0e-9a2f-1d8e5b6c7a90",
  "question_id": "Q2",
  "kind": "text",
  "received_at": "2026-11-02T08:20:11Z",
  "status": "received"
}
```

| Field | Type | Description |
|---|---|---|
| `answer_id` | string | The current answer's id (unchanged on replay) |
| `question_id` | string | Echo of the path param |
| `kind` | string | `"text"` |
| `received_at` | string (datetime) | When the current answer was submitted |
| `status` | string | Always `"received"` |

**Errors:**

| Code | When | `detail` |
|---|---|---|
| 401 | Header missing / malformed / unknown or rotated token | `invalid or missing candidate token` |
| 404 | `question_id` is not an existing question | `question not found` |
| 409 | Unanswered question that is not the current one | `answer the current question first` |
| 409 | Interview closed, different content sent | `interview is closed` |
| 409 | Concurrent different submission for the same question | `another submission for this question is in progress, please retry` |
| 422 | `text` blank after trim | `text: must not be blank` |
| 422 | `text` over 10 000 characters | `text: must be at most 10000 characters` |
| 422 | Body or `text` field missing | `body: Field required` or `text: Field required` |

---

### PUT /api/candidate/answers/{question_id}/audio

Submit or replace an audio answer (`multipart/form-data`, field `file`). Same receipt and the same `201`/`200`, supersede, order and closed rules as the text endpoint. The file is streamed to disk with a size cap and stored under the upload directory; `415`/`413`/`422` failures leave no file behind.

**Auth:** candidate token — `Authorization: Bearer <token>`

**Request:**

| Field | Type | Required | Rules |
|---|---|---|---|
| `question_id` | path param | yes | An existing question id |
| `file` | file (multipart) | yes | Extension `.m4a` `.mp3` `.wav` `.webm` `.ogg` `.mp4`; content-type `audio/*` (or `video/mp4`, `video/webm` for browser recorders); > 0 bytes, ≤ 25 MB |

```
Content-Type: multipart/form-data; boundary=...
file: clip.m4a (audio/mp4)
```

**Response 201** (new or replaced answer) / **200** (identical replay — same bytes as the current answer)

```json
{
  "answer_id": "9d2e5b6c-1a4f-4b8c-8e7d-2c6a9f0b3d41",
  "question_id": "Q2",
  "kind": "audio",
  "received_at": "2026-11-02T08:25:40Z",
  "status": "received"
}
```

| Field | Type | Description |
|---|---|---|
| `answer_id` | string | The current answer's id (unchanged on replay) |
| `question_id` | string | Echo of the path param |
| `kind` | string | `"audio"` |
| `received_at` | string (datetime) | When the current answer was submitted |
| `status` | string | Always `"received"` |

**Errors:**

| Code | When | `detail` |
|---|---|---|
| 401 | Header missing / malformed / unknown or rotated token | `invalid or missing candidate token` |
| 404 | `question_id` is not an existing question | `question not found` |
| 409 | Unanswered question that is not the current one | `answer the current question first` |
| 409 | Interview closed, different content sent | `interview is closed` |
| 409 | Concurrent different submission for the same question | `another submission for this question is in progress, please retry` |
| 413 | File bigger than the server cap | `audio file too large (max 25 MB)` |
| 415 | Extension or content type not allowed | `unsupported audio type` |
| 422 | `file` field missing | `file: Field required` |
| 422 | Uploaded file has 0 bytes | `audio file is empty` |

---

### POST /api/hr/session

MOCK sign-in. The only account is `HR_EMAIL`/`HR_PASSWORD` from `apps/api/.env`; anyone may reach this endpoint but only that account succeeds. On success sets an httpOnly `hr_session` cookie (SameSite=Lax, Path=/, Max-Age = `HR_SESSION_TTL_HOURS` hours, `Secure` only when `HR_COOKIE_SECURE`).

**Auth:** none (public; only the `.env` account can sign in)

**Request:**

| Field | Type | Required | Rules |
|---|---|---|---|
| `email` | string (JSON body) | yes | 1–255 chars; compared trimmed and case-insensitively |
| `password` | string (JSON body) | yes | 1–255 chars |

```json
{ "email": "hr@example.com", "password": "hr-demo-password" }
```

**Response 200**

```json
{ "email": "hr@example.com", "expires_at": "2026-11-02T20:00:00Z" }
```

| Field | Type | Description |
|---|---|---|
| `email` | string | The canonical `.env` account email |
| `expires_at` | string (datetime) | Session expiry; always carries a UTC offset |

**Errors:**

| Code | When | `detail` |
|---|---|---|
| 401 | Email or password does not match the `.env` account | `invalid email or password` |
| 415 | `Content-Type` is not `application/json` | `content type must be application/json` |
| 422 | `email` or `password` missing | `email: Field required` or `password: Field required` |
| 503 | `HR_EMAIL`/`HR_PASSWORD` not configured | `hr sign-in is not configured` |

---

### GET /api/hr/session

Who am I — returns the current HR session.

**Auth:** `hr_session` cookie

**Request:** no parameters, no body.

**Response 200**

```json
{ "email": "hr@example.com", "expires_at": "2026-11-02T20:00:00Z" }
```

| Field | Type | Description |
|---|---|---|
| `email` | string | The `.env` account email |
| `expires_at` | string (datetime) | Session expiry; always carries a UTC offset |

**Errors:**

| Code | When | `detail` |
|---|---|---|
| 401 | Missing, unknown, expired, or revoked (`.env` account changed) cookie | `invalid or missing hr session` |

---

### DELETE /api/hr/session

Sign out: deletes the session row and clears the cookie. Idempotent — always 204, even without a cookie.

**Auth:** none (idempotent; deletes the session row only if the cookie names one)

**Request:** no parameters, no body.

**Response 204** — empty body; do not parse JSON.

```json
{ "detail": "…" }
```

The shared error shape above is shown for reference; this endpoint returns no body on success and has no documented errors.

**Errors:** none — always `204`.

---

### GET /api/hr/roles

All roles with candidate counts and per-status scoring-job counts. Scoring job statuses are `queued`/`running`/`scored`/`failed`/`needs_person`/`superseded`; the UI shows `running` as "queued" (the brief's four statuses) and `superseded` jobs are never counted here.

**Auth:** `hr_session` cookie

**Request:** no parameters, no body.

**Response 200**

```json
{
  "roles": [
    {
      "id": 1,
      "title": "Backend Engineer",
      "candidate_count": 4,
      "job_counts": { "queued": 2, "running": 0, "scored": 1, "failed": 0, "needs_person": 1 }
    }
  ]
}
```

| Field | Type | Description |
|---|---|---|
| `roles` | array | Sorted by `title` |
| `roles[].id` | number | Role id |
| `roles[].title` | string | Role title |
| `roles[].candidate_count` | number | Candidates assigned to the role |
| `roles[].job_counts` | object | Jobs on candidates' current answers, keyed by status (always all five keys) |

**Errors:**

| Code | When | `detail` |
|---|---|---|
| 401 | Missing / invalid `hr_session` cookie | `invalid or missing hr session` |

---

### GET /api/hr/roles/{role_id}/candidates

Candidates for one role with review aggregates, sorted by name.

`avg_suggested` counts **scored** jobs only — a `needs_person` suggestion is one the model didn't trust, so it stays out. `avg_final` averages each candidate's final scores (newest HR decision, else the suggestion of a `scored` job). Both are `null` when there is nothing to average.

**Auth:** `hr_session` cookie

**Request:**

| Field | Type | Required | Rules |
|---|---|---|---|
| `role_id` | path param | yes | An existing role id |

**Response 200**

```json
{
  "role": { "id": 1, "title": "Backend Engineer" },
  "total_questions": 6,
  "candidates": [
    {
      "id": "C2041",
      "name": "Nhi Van Tran",
      "answered_count": 6,
      "total_questions": 6,
      "avg_suggested": 3.25,
      "avg_final": 3.4,
      "job_counts": { "queued": 0, "running": 0, "scored": 4, "failed": 1, "needs_person": 1 },
      "last_activity_at": "2026-09-14T09:41:00Z"
    }
  ]
}
```

| Field | Type | Description |
|---|---|---|
| `role` | object | `{id, title}` of the role |
| `total_questions` | number | Interview length (same for every candidate) |
| `candidates` | array | Sorted by `name` |
| `candidates[].id` | string | Candidate id |
| `candidates[].name` | string | Display name |
| `candidates[].answered_count` | number | Questions with a current answer |
| `candidates[].avg_suggested` | number \| null | Mean suggested score over `scored` jobs, 2 dp |
| `candidates[].avg_final` | number \| null | Mean final score over answers that have one, 2 dp |
| `candidates[].job_counts` | object | Current answers' jobs by status (five keys) |
| `candidates[].last_activity_at` | string (datetime) \| null | Latest answer submission, UTC |

**Errors:**

| Code | When | `detail` |
|---|---|---|
| 401 | Missing / invalid `hr_session` cookie | `invalid or missing hr session` |
| 404 | `role_id` unknown | `role not found` |

---

### GET /api/hr/candidates/{candidate_id}

The full review of one candidate: every question in position order with its rubric, the current answer (which submission counts), its scoring job, suggestion, and HR decision history, plus earlier replaced submissions and their decisions.

Which submission counts: the **current** answer (latest, not superseded). A resubmission starts a fresh final score; earlier submissions stay visible under `earlier_submissions` with their `superseded_at` and decisions.

`suggested_score`/`suggested_reason` are present only when the job is `scored` or `needs_person`; a `failed` job never carries a score. `final_source` is `"hr"` when the newest decision sets the final score, `"suggested"` when it comes from a `scored` job, `null` when there is no final score (e.g. `needs_person` waits for an HR override).

**Auth:** `hr_session` cookie

**Request:**

| Field | Type | Required | Rules |
|---|---|---|---|
| `candidate_id` | path param | yes | An existing candidate id |

**Response 200**

```json
{
  "id": "C2041",
  "name": "Nhi Van Tran",
  "email": "nhi@example.com",
  "role": { "id": 1, "title": "Backend Engineer" },
  "total_questions": 6,
  "answered_count": 6,
  "avg_suggested": 3.25,
  "avg_final": 3.4,
  "job_counts": { "queued": 0, "running": 0, "scored": 4, "failed": 1, "needs_person": 1 },
  "questions": [
    {
      "question": { "id": "Q1", "position": 1, "text": "…", "rubric": { "1": "…", "2": "…", "3": "…", "4": "…" } },
      "answer": {
        "id": "A001",
        "kind": "text",
        "text": "…",
        "audio": null,
        "submitted_at": "2026-09-14T09:41:00Z",
        "submission_count": 1,
        "job": {
          "id": 12, "status": "scored", "attempts": 1, "last_error": null,
          "suggested_score": 3, "suggested_reason": "…", "needs_person_reason": null,
          "model": "gemini-…", "updated_at": "2026-09-14T09:42:10Z"
        },
        "final_score": 3,
        "final_source": "suggested",
        "decisions": [],
        "earlier_submissions": []
      }
    }
  ]
}
```

| Field | Type | Description |
|---|---|---|
| `id`, `name`, `email` | string | Candidate identity (HR only — never exposed on candidate routes) |
| `role` | object | `{id, title}` |
| `questions[].question.rubric` | object | Score descriptions keyed `"1"`–`"4"` |
| `questions[].answer` | object \| null | Current answer; `null` when unanswered |
| `answer.kind` | string | `"text"` or `"audio"` |
| `answer.audio` | object \| null | `{content_type, size_bytes, url}` for audio answers; `content_type` from the file extension, `url` is the HR playback route |
| `answer.submission_count` | number | 1 + number of superseded versions |
| `answer.job` | object \| null | Scoring job; `suggested_score`/`suggested_reason` non-null only for `scored`/`needs_person` |
| `answer.final_score` | number \| null | Newest decision's score, else the `scored` suggestion |
| `answer.final_source` | string \| null | `"hr"`, `"suggested"`, or `null` |
| `answer.decisions[]` | array | Newest first: `{id, kind, score, reason, hr_email, created_at}` |
| `answer.earlier_submissions[]` | array | Superseded versions, newest first: `{id, kind, text, audio, submitted_at, superseded_at, decisions}` — decisions stay visible after a resubmission |

**Errors:**

| Code | When | `detail` |
|---|---|---|
| 401 | Missing / invalid `hr_session` cookie | `invalid or missing hr session` |
| 404 | `candidate_id` unknown | `candidate not found` |

---

### GET /api/hr/jobs

Scoring jobs across all candidates, newest `updated_at` first. By default `superseded` jobs are excluded; `?status=<status>` filters to exactly one status. `counts` always covers all six statuses across all jobs.

**Auth:** `hr_session` cookie

**Request:**

| Field | Type | Required | Rules |
|---|---|---|---|
| `status` | query param | no | One of `queued`, `running`, `scored`, `failed`, `needs_person`, `superseded` |

**Response 200**

```json
{
  "counts": { "queued": 3, "running": 0, "scored": 10, "failed": 2, "needs_person": 1, "superseded": 4 },
  "jobs": [
    {
      "id": 12, "status": "failed", "attempts": 3, "last_error": "timeout",
      "needs_person_reason": null, "updated_at": "2026-09-14T09:42:10Z",
      "answer": { "id": "A001", "kind": "text", "question_id": "Q1" },
      "candidate": { "id": "C2041", "name": "Nhi Van Tran" },
      "role": { "id": 1, "title": "Backend Engineer" }
    }
  ]
}
```

| Field | Type | Description |
|---|---|---|
| `counts` | object | Job counts for **all six** statuses |
| `jobs[].id` | number | Job id (used by retry) |
| `jobs[].status` | string | One of the six statuses |
| `jobs[].attempts` | number | Scoring attempts so far |
| `jobs[].last_error` | string \| null | Last failure message |
| `jobs[].needs_person_reason` | string \| null | Why the model asked for a person |
| `jobs[].answer` | object | `{id, kind, question_id}` of the scored answer |
| `jobs[].candidate` | object | `{id, name}` |
| `jobs[].role` | object | `{id, title}` |

`jobs[]` items carry no score fields — read scores through the candidate review.

**Errors:**

| Code | When | `detail` |
|---|---|---|
| 401 | Missing / invalid `hr_session` cookie | `invalid or missing hr session` |
| 422 | `status` not a known status | `status: Input should be 'queued', 'running', 'scored', 'failed', 'needs_person' or 'superseded'` |

---

### GET /api/hr/answers/{answer_id}/audio

Streams a candidate's audio answer. The response content type is chosen from a fixed extension map (`.m4a`/`.mp4` → `audio/mp4`, `.mp3` → `audio/mpeg`, `.wav` → `audio/wav`, `.webm` → `audio/webm`, `.ogg` → `audio/ogg`) — never from the uploaded content-type header, which is candidate-controlled. Sent with `X-Content-Type-Options: nosniff` and a sandboxed `Content-Security-Policy`. Supports `Range` (`Accept-Ranges: bytes`): a valid range returns 206, an unsatisfiable one returns 416 (Starlette's body, not `{"detail": …}`).

**Auth:** `hr_session` cookie

**Request:**

| Field | Type | Required | Rules |
|---|---|---|---|
| `answer_id` | path param | yes | An existing audio answer id |
| `Range` | header | no | e.g. `bytes=0-1023` |

**Response 200** — audio bytes (`Content-Type` from the extension map).

**Response 206** — the requested byte range (`Content-Range` set).

```json
{ "detail": "audio not found" }
```

(Error example shown — the success body is raw bytes, not JSON.)

**Errors:**

| Code | When | `detail` |
|---|---|---|
| 401 | Missing / invalid `hr_session` cookie | `invalid or missing hr session` |
| 404 | Answer unknown, not an audio answer, file missing, path outside the upload dir, or unmapped extension | `audio not found` |
| 416 | Unsatisfiable `Range` header | (Starlette body — not `{"detail": …}`) |

---

### POST /api/hr/answers/{answer_id}/override

HR overrides a score with a mandatory reason. Decisions are **append-only**: the newest row counts, earlier reasons are kept. An identical repeat of the newest decision returns `200` with the same row (safe double-click); a different decision appends a new row (`201`). Override is allowed for any job status — it is the only way to score an audio answer, and it wins over a later suggestion in `final_score`. Only the **current** answer can be decided; a replaced submission keeps its history but can't take new decisions.

**Auth:** `hr_session` cookie + `Content-Type: application/json`

**Request:**

| Field | Type | Required | Rules |
|---|---|---|---|
| `answer_id` | path param | yes | An existing, current (not superseded) answer id |
| `score` | number (JSON body) | yes | Integer 1–4 |
| `reason` | string (JSON body) | yes | Non-blank after trim, ≤ 2000 characters |

```json
{ "score": 4, "reason": "Clearly strong on systems design." }
```

**Response 201** (new decision) / **Response 200** (identical repeat of the newest decision)

```json
{
  "id": 7,
  "answer_id": "A001",
  "kind": "override",
  "score": 4,
  "reason": "Clearly strong on systems design.",
  "hr_email": "hr@example.com",
  "created_at": "2026-11-02T16:30:00Z"
}
```

| Field | Type | Description |
|---|---|---|
| `id` | number | Decision id |
| `answer_id` | string | The decided answer |
| `kind` | string | `"override"` |
| `score` | number | The override score 1–4 |
| `reason` | string | HR's reason (required for overrides) |
| `hr_email` | string | The `.env` account that decided |
| `created_at` | string (datetime) | UTC timestamp |

**Errors:**

| Code | When | `detail` |
|---|---|---|
| 401 | Missing / invalid `hr_session` cookie | `invalid or missing hr session` |
| 404 | `answer_id` unknown | `answer not found` |
| 409 | Answer superseded by a newer submission | `answer has been replaced by a newer submission` |
| 409 | A different decision was saved concurrently | `another decision for this answer was just saved, reload and try again` |
| 415 | `Content-Type` is not `application/json` | `content type must be application/json` |
| 422 | `score` missing | `score: Field required` |
| 422 | `score` outside 1–4 | `score: Input should be less than or equal to 4` (or `greater than or equal to 1`) |
| 422 | `reason` blank after trim | `reason: must not be blank` |
| 422 | `reason` over 2000 characters | `reason: must be at most 2000 characters` |

---

### POST /api/hr/answers/{answer_id}/accept

HR accepts the suggested score. Only valid on a `scored` job whose current suggestion equals the posted score — posting a different score means the suggestion changed under you (`409`). A `needs_person` answer can't be accepted at all: it needs an override with a reason. Same idempotency as override: identical repeat → `200`, new decision → `201`. Accepted decisions carry `reason: null` and count as a `"hr"` final score.

**Auth:** `hr_session` cookie + `Content-Type: application/json`

**Request:**

| Field | Type | Required | Rules |
|---|---|---|---|
| `answer_id` | path param | yes | An existing, current answer id |
| `score` | number (JSON body) | yes | Integer 1–4, equal to the current suggestion |

```json
{ "score": 3 }
```

**Response 201** / **Response 200** (identical repeat)

```json
{
  "id": 8,
  "answer_id": "A001",
  "kind": "accept",
  "score": 3,
  "reason": null,
  "hr_email": "hr@example.com",
  "created_at": "2026-11-02T16:31:00Z"
}
```

| Field | Type | Description |
|---|---|---|
| `id` | number | Decision id |
| `answer_id` | string | The decided answer |
| `kind` | string | `"accept"` |
| `score` | number | The accepted score |
| `reason` | string \| null | Always `null` for accept |
| `hr_email` | string | The `.env` account that decided |
| `created_at` | string (datetime) | UTC timestamp |

**Errors:**

| Code | When | `detail` |
|---|---|---|
| 401 | Missing / invalid `hr_session` cookie | `invalid or missing hr session` |
| 404 | `answer_id` unknown | `answer not found` |
| 409 | Answer superseded by a newer submission | `answer has been replaced by a newer submission` |
| 409 | Job not `scored` (queued/running/failed/superseded, or no suggestion) | `no suggested score to accept` |
| 409 | Job is `needs_person` — a person must override with a reason | `needs a person: use override with a reason` |
| 409 | Posted score ≠ the current suggestion | `suggested score has changed, reload and try again` |
| 409 | A different decision was saved concurrently | `another decision for this answer was just saved, reload and try again` |
| 415 | `Content-Type` is not `application/json` | `content type must be application/json` |
| 422 | `score` missing or outside 1–4 | `score: Field required` / `score: Input should be …` |

---

### POST /api/hr/jobs/{job_id}/retry

Re-queue a `failed` scoring job: status → `queued`, `attempts` → 0, `last_error` and all score columns cleared. Idempotent: a repeat (or concurrent double click) while already `queued` returns `200` unchanged. The scoring worker picks `queued` jobs up on its next poll.

**Auth:** `hr_session` cookie + `Content-Type: application/json`

**Request:** empty JSON body `{}` — required for the JSON content-type rule.

```json
{}
```

**Response 200** — the job view (both when changed and on a no-op repeat)

```json
{
  "id": 12,
  "status": "queued",
  "attempts": 0,
  "last_error": null,
  "suggested_score": null,
  "suggested_reason": null,
  "needs_person_reason": null,
  "model": "gemini-…",
  "updated_at": "2026-11-02T16:32:00Z"
}
```

| Field | Type | Description |
|---|---|---|
| `id` | number | Job id |
| `status` | string | `"queued"` after retry |
| `attempts` | number | Reset to `0` |
| `last_error` | string \| null | Cleared |
| `suggested_score` | number \| null | Cleared — a retried job carries no score |
| `suggested_reason` | string \| null | Cleared |
| `needs_person_reason` | string \| null | Cleared |
| `model` | string \| null | Last model that ran (history) |
| `updated_at` | string (datetime) | UTC timestamp |

**Errors:**

| Code | When | `detail` |
|---|---|---|
| 401 | Missing / invalid `hr_session` cookie | `invalid or missing hr session` |
| 404 | `job_id` unknown | `job not found` |
| 409 | Job is not `failed` and not already `queued` (e.g. `scored`, `running`, `needs_person`, `superseded`) | `only failed jobs can be retried` |
| 415 | `Content-Type` is not `application/json` (incl. missing body) | `content type must be application/json` |

---

## Scoring job status reference

`scoring_jobs` is the durable queue for the background scoring worker (`python -m app.worker`). These values appear on `GET /api/hr/jobs`, the candidate review, and the retry endpoint. No endpoint change.

| status | meaning | score fields |
|---|---|---|
| `queued` | waiting for the worker (also after a rate-limit pause) | null |
| `running` | worker is scoring it. `attempts` = number of worker runs (claims) | null |
| `scored` | model suggestion validated and stored | `suggested_score` 1–4, `suggested_reason`, `model` |
| `needs_person` | HR must read it — see `needs_person_reason`. No suggestion; HR overrides | null |
| `failed` | gave up — see `last_error`. Never a low score. Retry via `POST /api/hr/jobs/{job_id}/retry` | null |
| `superseded` | candidate replaced the answer | as left |

`needs_person_reason` values:

- `audio answer, not transcribed (transcription not built)`
- `empty answer`
- `answer appears to address the scorer, HR to read. Candidate text: "…"`
- `model flagged instructions to the scorer`
- `model declined to score: <REASON>`
