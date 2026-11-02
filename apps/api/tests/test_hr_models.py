import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.time import utcnow
from app.models import HrSession, ScoreDecision, ScoringJob
from app.models.enums import JobStatus
from app.models.scoring_job import validate_job_result

from .factories import add_decision, answer_one, make_candidate, make_role, seed_questions


@pytest.fixture
def answer(db_session):
    role = make_role(db_session)
    seed_questions(db_session)
    candidate, _ = make_candidate(db_session, role)
    return answer_one(db_session, candidate, "Q1")


def _decision(answer_id, *, sequence=1, kind="override", score=3, reason="why"):
    return ScoreDecision(
        answer_id=answer_id,
        sequence=sequence,
        kind=kind,
        score=score,
        reason=reason,
        hr_email="hr@test.local",
    )


def test_decision_sequence_unique_per_answer(db_session, answer):
    add_decision(db_session, answer, score=3, reason="first")
    db_session.add(_decision(answer.id, sequence=1, score=4, reason="dup"))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_decision_score_out_of_range_rejected(db_session, answer):
    for bad in (0, 5):
        db_session.add(_decision(answer.id, sequence=10 + bad, score=bad))
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()


def test_decision_kind_must_be_valid(db_session, answer):
    db_session.add(_decision(answer.id, sequence=2, kind="bogus"))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_override_decision_requires_reason(db_session, answer):
    db_session.add(_decision(answer.id, sequence=2, kind="override", reason=None))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_session_token_hash_unique(db_session):
    db_session.add(
        HrSession(
            token_hash="a" * 64,
            email="hr@test.local",
            credential_fingerprint="fp",
            created_at=utcnow(),
            expires_at=utcnow(),
        )
    )
    db_session.commit()
    db_session.add(
        HrSession(
            token_hash="a" * 64,
            email="hr@test.local",
            credential_fingerprint="fp",
            created_at=utcnow(),
            expires_at=utcnow(),
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


@pytest.mark.parametrize("status", ["failed", "queued", "running"])
def test_non_scored_job_cannot_hold_a_score(db_session, answer, status):
    job = db_session.scalar(select(ScoringJob).where(ScoringJob.answer_id == answer.id))
    job.status = status
    job.suggested_score = 2
    with pytest.raises(ValueError):
        db_session.commit()
    db_session.rollback()


def test_scored_job_needs_score_and_reason(db_session, answer):
    job = db_session.scalar(select(ScoringJob).where(ScoringJob.answer_id == answer.id))
    job.status = JobStatus.SCORED
    with pytest.raises(ValueError):
        db_session.commit()
    db_session.rollback()

    job.suggested_score = 3
    with pytest.raises(ValueError):
        db_session.commit()
    db_session.rollback()


def test_job_score_out_of_range_rejected(db_session, answer):
    job = db_session.scalar(select(ScoringJob).where(ScoringJob.answer_id == answer.id))
    for bad in (0, 5):
        with pytest.raises(ValueError):
            job.suggested_score = bad


def test_needs_person_job_requires_reason(db_session, answer):
    job = db_session.scalar(select(ScoringJob).where(ScoringJob.answer_id == answer.id))
    job.status = JobStatus.NEEDS_PERSON
    with pytest.raises(ValueError):
        db_session.commit()
    db_session.rollback()


def test_valid_job_results_flush(db_session, answer):
    job = db_session.scalar(select(ScoringJob).where(ScoringJob.answer_id == answer.id))
    job.status = JobStatus.SCORED
    job.suggested_score = 3
    job.suggested_reason = "solid"
    db_session.commit()

    job.status = JobStatus.NEEDS_PERSON
    job.suggested_score = 2
    job.needs_person_reason = "unclear audio"
    db_session.commit()

    job.status = JobStatus.SUPERSEDED
    db_session.commit()


def test_validate_job_result_unit():
    with pytest.raises(ValueError):
        validate_job_result("failed", 2, None, None)
    with pytest.raises(ValueError):
        validate_job_result("scored", None, None, None)
    with pytest.raises(ValueError):
        validate_job_result("scored", 3, None, None)
    with pytest.raises(ValueError):
        validate_job_result("scored", 5, "ok", None)
    with pytest.raises(ValueError):
        validate_job_result("needs_person", None, None, None)
    # valid outcomes do not raise
    validate_job_result("scored", 3, "solid", None)
    validate_job_result("needs_person", 2, "maybe", "unclear audio")
    validate_job_result("failed", None, None, None)
    validate_job_result("superseded", 2, "kept", None)
