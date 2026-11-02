from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.models import Candidate, HrSession
from app.services.candidate_access import find_candidate_by_token
from app.services.hr_auth import find_session

_INVALID_TOKEN = "invalid or missing candidate token"
_INVALID_HR_SESSION = "invalid or missing hr session"
_JSON_REQUIRED = "content type must be application/json"


def get_current_candidate(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> Candidate:
    """Resolve `Authorization: Bearer <token>` to a candidate.

    Every failure returns the same 401 detail so tokens can't be probed.
    """
    raw = ""
    if authorization and authorization.startswith("Bearer "):
        raw = authorization.removeprefix("Bearer ").strip()
    candidate = find_candidate_by_token(db, raw) if raw else None
    if candidate is None:
        raise HTTPException(status_code=401, detail=_INVALID_TOKEN)
    return candidate


def get_current_hr(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> HrSession:
    """Resolve the `hr_session` cookie to a session row.

    HR auth reads only the cookie and ignores `Authorization` entirely, so
    a candidate Bearer token can never open an /api/hr/* route.
    """
    raw = request.cookies.get("hr_session", "")
    session = find_session(db, raw, settings) if raw else None
    if session is None:
        raise HTTPException(status_code=401, detail=_INVALID_HR_SESSION)
    return session


def require_json_content_type(request: Request) -> None:
    """HR POSTs must send `Content-Type: application/json`.

    This is also the CSRF mitigation: the API mounts no CORS middleware, so
    a cross-origin JSON request fails preflight, and an HTML form can't
    send JSON at all. SameSite is not relied on alone.
    """
    if request.method in ("POST", "PUT", "PATCH"):
        media_type = request.headers.get("content-type", "").split(";")[0].strip().lower()
        if media_type != "application/json":
            raise HTTPException(status_code=415, detail=_JSON_REQUIRED)
