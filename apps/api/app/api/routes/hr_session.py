from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_hr, require_json_content_type
from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.models import HrSession
from app.schemas.hr import HrSessionView, HrSignIn
from app.services.hr_auth import (
    _hash_token,
    create_session,
    delete_session,
    verify_credentials,
)

router = APIRouter(prefix="/hr", tags=["hr"])


@router.post(
    "/session",
    response_model=HrSessionView,
    dependencies=[Depends(require_json_content_type)],
)
def sign_in(
    body: HrSignIn,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """MOCK sign-in: the only account is HR_EMAIL/HR_PASSWORD from .env."""
    if not settings.HR_EMAIL or not settings.HR_PASSWORD:
        raise HTTPException(status_code=503, detail="hr sign-in is not configured")
    if not verify_credentials(settings, body.email, body.password):
        raise HTTPException(status_code=401, detail="invalid email or password")
    raw = create_session(db, settings)
    # Fetch the row directly: find_session filters on expiry, which would
    # hide a session created with a misconfigured non-positive TTL.
    session = db.scalar(select(HrSession).where(HrSession.token_hash == _hash_token(raw)))
    response.set_cookie(
        "hr_session",
        raw,
        max_age=settings.HR_SESSION_TTL_HOURS * 3600,
        httponly=True,
        samesite="lax",
        secure=settings.HR_COOKIE_SECURE,
        path="/",
    )
    return HrSessionView(email=session.email, expires_at=session.expires_at)


@router.get("/session", response_model=HrSessionView)
def get_session(session: HrSession = Depends(get_current_hr)):
    return HrSessionView(email=session.email, expires_at=session.expires_at)


@router.delete("/session", status_code=204)
def sign_out(request: Request, db: Session = Depends(get_db)):
    raw = request.cookies.get("hr_session")
    if raw:
        delete_session(db, raw)
    resp = Response(status_code=204)
    resp.delete_cookie("hr_session", path="/")
    return resp
