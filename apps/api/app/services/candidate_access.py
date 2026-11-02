import hashlib
import secrets

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.time import utcnow
from app.models import Candidate


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def issue_token(db: Session, candidate: Candidate) -> str:
    """Issue a new access token for a candidate.

    Returns the raw token (shown once, e.g. in a seeded link). Only its
    sha256 is stored; re-issuing revokes the previous token. Flushes but
    does not commit — the caller owns the transaction boundary.
    """
    raw = secrets.token_urlsafe(32)
    candidate.access_token_hash = _hash_token(raw)
    candidate.token_issued_at = utcnow()
    db.flush()
    return raw


def find_candidate_by_token(db: Session, raw: str) -> Candidate | None:
    if not raw:
        return None
    return db.scalar(select(Candidate).where(Candidate.access_token_hash == _hash_token(raw)))
