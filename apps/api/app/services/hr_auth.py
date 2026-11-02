import hashlib
import hmac
import secrets
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.time import utcnow
from app.models import HrSession


def verify_credentials(settings: Settings, email: str, password: str) -> bool:
    """True only for the single MOCK account configured in .env."""
    if not settings.HR_EMAIL or not settings.HR_PASSWORD:
        return False
    email_ok = hmac.compare_digest(
        email.strip().casefold().encode(), settings.HR_EMAIL.strip().casefold().encode()
    )
    password_ok = hmac.compare_digest(password.encode(), settings.HR_PASSWORD.encode())
    return email_ok and password_ok


def credential_fingerprint(settings: Settings) -> str | None:
    """Ties a session to the current .env account.

    Changing HR_EMAIL/HR_PASSWORD (or unsetting them) changes the
    fingerprint, revoking every issued session on the next request.
    """
    if not settings.HR_EMAIL or not settings.HR_PASSWORD:
        return None
    return hmac.new(
        settings.HR_PASSWORD.encode(),
        settings.HR_EMAIL.strip().casefold().encode(),
        hashlib.sha256,
    ).hexdigest()


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def create_session(db: Session, settings: Settings) -> str:
    """Create a session row; returns the raw token (shown once, never stored)."""
    raw = secrets.token_urlsafe(32)
    session = HrSession(
        token_hash=_hash_token(raw),
        email=settings.HR_EMAIL.strip(),
        credential_fingerprint=credential_fingerprint(settings),
        created_at=utcnow(),
        expires_at=utcnow() + timedelta(hours=settings.HR_SESSION_TTL_HOURS),
    )
    db.add(session)
    db.commit()
    return raw


def find_session(db: Session, raw: str, settings: Settings) -> HrSession | None:
    """Look up a live session by raw token, bound to the current account."""
    if not raw:
        return None
    # Expiry is checked in SQL, not Python: SQLite returns naive datetimes
    # and comparing them to an aware utcnow() raises TypeError.
    row = db.scalar(
        select(HrSession).where(
            HrSession.token_hash == _hash_token(raw),
            HrSession.expires_at > utcnow(),
        )
    )
    if row is None:
        return None
    fingerprint = credential_fingerprint(settings)
    if fingerprint is None or not hmac.compare_digest(row.credential_fingerprint, fingerprint):
        return None
    return row


def delete_session(db: Session, raw: str) -> None:
    if not raw:
        return
    row = db.scalar(select(HrSession).where(HrSession.token_hash == _hash_token(raw)))
    if row is not None:
        db.delete(row)
        db.commit()
