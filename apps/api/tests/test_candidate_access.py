import hashlib

from app.services.candidate_access import find_candidate_by_token, issue_token

from .factories import make_candidate, make_role


def test_issue_token_stores_only_hash(db_session):
    role = make_role(db_session)
    candidate, _ = make_candidate(db_session, role, with_token=False)

    raw = issue_token(db_session, candidate)
    db_session.commit()

    assert isinstance(raw, str) and raw
    db_session.refresh(candidate)
    assert candidate.access_token_hash == hashlib.sha256(raw.encode()).hexdigest()
    assert raw not in (candidate.access_token_hash or "")
    assert candidate.token_issued_at is not None


def test_find_candidate_by_token_roundtrip(db_session):
    role = make_role(db_session)
    candidate, raw = make_candidate(db_session, role)

    assert find_candidate_by_token(db_session, raw).id == candidate.id
    assert find_candidate_by_token(db_session, "not-a-real-token") is None


def test_reissue_revokes_old_token(db_session):
    role = make_role(db_session)
    candidate, old_raw = make_candidate(db_session, role)

    new_raw = issue_token(db_session, candidate)
    db_session.commit()

    assert new_raw != old_raw
    assert find_candidate_by_token(db_session, old_raw) is None
    assert find_candidate_by_token(db_session, new_raw).id == candidate.id
