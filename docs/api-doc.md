# API Documentation

**Base URL:** `/api` (via Next.js rewrite — use this from browser code). Direct: `http://localhost:8000/api` (server-side fetches, scripts, curl).

**Auth model:**
- `candidate token` — a personal, reusable link token. The web app serves it at `/i/<token>`; clients send it as `Authorization: Bearer <token>`. Stored hashed (sha256) in the database; rotated by `make seed` (old links stop working).
- `hr session (mocked)` — mock sign-in, labelled in UI

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
