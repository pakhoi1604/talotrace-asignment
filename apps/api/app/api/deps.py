from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Candidate
from app.services.candidate_access import find_candidate_by_token

_INVALID_TOKEN = "invalid or missing candidate token"


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
