---
phase: 3
title: "HR auth: session endpoints"
status: done
priority: P1
dependencies: [2]
---

# Phase 3: HR auth: session endpoints

## Overview
Mock single-account sign-in, cookie session tied to the current `.env` account, `get_current_hr` and `require_json_content_type` dependencies used by every later HR route. Done = `test_hr_auth.py` green (the route-table test in `test_hr_permissions.py` stays red until phase 5).

## Requirements
- Functional: sign in with the `.env` account only; read session; sign out; sessions die when the account changes or is removed.
- Non-functional: constant-time compares; raw session token never stored or logged; HR auth ignores `Authorization` completely; the same 401 message for every failure; no Python-side comparison of DB datetimes.

## Architecture

### `app/services/hr_auth.py` (no FastAPI imports)
```python
def verify_credentials(settings, email: str, password: str) -> bool
    # False if HR_EMAIL or HR_PASSWORD is None
    # email: hmac.compare_digest(strip+casefold(typed), casefold(HR_EMAIL)); password: compare_digest on utf-8 bytes
def credential_fingerprint(settings) -> str | None
    # None if unconfigured; else hmac_sha256(key=HR_PASSWORD, msg=casefold(HR_EMAIL)).hexdigest()
def create_session(db, settings) -> str
    # token_urlsafe(32); stores sha256(raw), email=settings.HR_EMAIL.strip() (canonical),
    # credential_fingerprint, expires_at = utcnow() + TTL; commits; returns raw
def find_session(db, raw: str, settings) -> HrSession | None
    # SELECT … WHERE token_hash = sha256(raw) AND expires_at > :utcnow   (expiry in SQL, never in Python)
    # then: fingerprint = credential_fingerprint(settings); None if fingerprint is None
    #       or not compare_digest(row.credential_fingerprint, fingerprint)
def delete_session(db, raw: str) -> None                      # no-op if missing
```
- **Expiry in SQL** because SQLite returns naive datetimes and `utcnow()` is aware. Comparing them in Python raises `TypeError`. <!-- Red Team: naive datetimes -->
- **Fingerprint** ties a session to the current account: changing `HR_PASSWORD` or `HR_EMAIL`, or unsetting them, revokes every existing cookie on the next request. <!-- Red Team: session revocation -->
- Expired rows aren't swept (tiny table).

### Dependencies (`app/api/deps.py`)
- `get_current_hr(request, db, settings) -> HrSession`: reads `request.cookies["hr_session"]` → `find_session` → returns the row (routes need `email` and `expires_at`); else 401 `invalid or missing hr session`. Never looks at `Authorization`.
- `require_json_content_type(request)`: for `POST`/`PUT`/`PATCH`, media type must be `application/json`, else 415 `content type must be application/json`. Cross-origin JSON requests need a CORS preflight, and the API has no CORS middleware, so a page on another origin, including another `localhost` port, can't make one. A plain HTML form can't send JSON. <!-- Red Team: CSRF -->
- Every HR router is created with `dependencies=[Depends(require_json_content_type), Depends(get_current_hr)]` at router level. The session router applies them per route: `POST` gets only `require_json_content_type`, `GET` only `get_current_hr`, `DELETE` neither. If body validation runs before the dependency and yields 422 instead of 415, move the content-type check into a tiny `APIRoute` subclass for HR routers. The 415 test pins the behaviour.

### Routes (`app/api/routes/hr_session.py`)
| Method | Path | Behaviour |
|---|---|---|
| POST | `/api/hr/session` | body `{email: str (1..255), password: str (1..255)}`. Creds unset → 503 `hr sign-in is not configured`. Wrong → 401 `invalid email or password`. OK → `create_session`, `Set-Cookie: hr_session=<raw>; HttpOnly; SameSite=Lax; Path=/; Max-Age=<ttl>` (+ `Secure` if `HR_COOKIE_SECURE`), 200 `{email, expires_at}` |
| GET | `/api/hr/session` | `get_current_hr` → 200 `{email, expires_at}`; else 401 |
| DELETE | `/api/hr/session` | delete row if cookie present, clear cookie, **204 with no body** (idempotent) |

Schemas (`app/schemas/hr.py`): `HrSignIn`, `HrSessionView{email, expires_at: UtcDatetime}`. `UtcDatetime` is created here in `app/schemas/common.py` (phase 4 reuses it): `Annotated[datetime, AfterValidator(attach_utc_if_naive)]`, so JSON always carries an offset.

### `docs/api-doc.md`
- Header **Auth model**: "`hr_session` cookie: **MOCK sign-in**, one account from `HR_EMAIL`/`HR_PASSWORD` in `apps/api/.env`. httpOnly, SameSite=Lax. Sessions end on sign-out, after `HR_SESSION_TTL_HOURS`, or when the `.env` account changes. HR routes read only this cookie; a candidate Bearer token is never accepted on `/api/hr/*`. HR `POST` routes require `Content-Type: application/json` (415 otherwise)."
- Frontend notes: browser calls go through `/api/*` (cookie sent automatically); server components calling `API_URL` must forward the incoming `cookie` header and render dynamically (no caching across sessions); `DELETE /api/hr/session` returns **204 with an empty body** (don't parse JSON).
- 3 endpoint sections with the full checklist (Auth, Request field table + example, one Response block per success code with JSON + field table, Errors table with exact `detail`).

### `apps/web/src/lib/api-types.ts`
`HrSignInRequest`, `HrSession`.

## Related Code Files
- Create: `apps/api/app/services/hr_auth.py`
- Modify: `apps/api/app/api/deps.py`: `get_current_hr`, `require_json_content_type`
- Create: `apps/api/app/schemas/common.py` (`UtcDatetime`), `apps/api/app/schemas/hr.py` (session schemas; more in phases 4–5)
- Create: `apps/api/app/api/routes/hr_session.py`
- Modify: `apps/api/app/main.py`: include router under `/api`
- Modify: `docs/api-doc.md`, `apps/web/src/lib/api-types.ts`

## Implementation Steps
1. Service → `test_hr_auth.py` service tests green, including second-session and revocation cases.
2. Dependencies + schemas + router + wiring → API tests green, including 415 and cookie flags.
3. Docs + types. `make lint`.

## Success Criteria
- [ ] `test_hr_auth.py` green with no test edits
- [ ] No Python comparison of DB-loaded datetimes anywhere in `hr_auth`
- [ ] Doc sections + types added; `make lint` green

## Risk Assessment
- Demo credentials in `.env.example` are live after `make setup` (user decision: keep for evaluators). Labelled MOCK; README and architecture.md state the risk and how to change them.
- No brute-force protection. Acceptable for a local mock; listed in "not built".
- The fingerprint is an unsalted HMAC of the demo password stored in the local DB. Acceptable for a mock single account; noted.
