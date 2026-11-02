# API Documentation

**Base URL:** `/api` (via Next.js rewrite — use this from browser code). Direct: `http://localhost:8000/api` (server-side fetches, scripts, curl).

**Auth model:**
- `candidate token` — single-use link token, candidate endpoints only
- `hr session (mocked)` — mock sign-in, labelled in UI

**Error shape:** `{ "detail": string }`

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
