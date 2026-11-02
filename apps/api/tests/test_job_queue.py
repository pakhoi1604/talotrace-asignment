from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.models import ScoringJob
from app.models.enums import JobStatus
from app.scoring.score_answer import ScoringOutcome
from app.worker import job_queue
from app.worker.job_queue import (
    claim_next_job,
    heartbeat,
    recover_stale_jobs,
    requeue_rate_limited,
    write_outcome,
)
from tests.factories import (
    make_candidate,
    make_role,
    make_text_answer,
    seed_questions,
    set_job_result,
)

NOW = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
LEASE = timedelta(seconds=120)


def job_of(db, answer) -> ScoringJob:
    return db.scalar(select(ScoringJob).where(ScoringJob.answer_id == answer.id))


@pytest.fixture
def queued_job(db_session):
    role = make_role(db_session)
    seed_questions(db_session)
    candidate, _ = make_candidate(db_session, role)
    answer = make_text_answer(db_session, candidate, "Q1", "answer one")
    return job_of(db_session, answer)


def fresh_status(db_session, job_id):
    db_session.expire_all()
    return db_session.get(ScoringJob, job_id)


# --- claim --------------------------------------------------------------------


def test_claim_takes_oldest_queued(db_session, queued_job):
    claim = claim_next_job(db_session, now=NOW)
    assert claim is not None
    assert claim.job_id == queued_job.id
    assert claim.claim_no == 1
    job = fresh_status(db_session, queued_job.id)
    assert job.status == JobStatus.RUNNING
    assert job.attempts == 1
    assert job.updated_at.replace(tzinfo=UTC) == NOW


def test_claim_empty_queue_returns_none(db_session):
    assert claim_next_job(db_session, now=NOW) is None


def test_claim_skips_to_next_job_on_race(db_session, session_factory, monkeypatch):
    role = make_role(db_session)
    seed_questions(db_session)
    candidate, _ = make_candidate(db_session, role)
    make_text_answer(db_session, candidate, "Q1", "first")
    second = job_of(db_session, make_text_answer(db_session, candidate, "Q2", "second"))

    real_next = job_queue._next_queued_id
    raced = {"done": False}

    def stealing_next(db):
        job_id = real_next(db)
        if not raced["done"] and job_id is not None:
            raced["done"] = True
            other = session_factory()
            try:
                stolen = claim_next_job(other, now=NOW)
                assert stolen.job_id == job_id  # second session took it
            finally:
                other.close()
        return job_id

    monkeypatch.setattr(job_queue, "_next_queued_id", stealing_next)
    claim = claim_next_job(db_session, now=NOW)

    assert claim is not None
    assert claim.job_id == second.id
    assert claim.claim_no == 1


def test_non_queued_jobs_never_claimed(db_session):
    role = make_role(db_session)
    seed_questions(db_session)
    candidate, _ = make_candidate(db_session, role)

    scored = make_text_answer(db_session, candidate, "Q1", "s")
    set_job_result(db_session, scored, status=JobStatus.SCORED, score=3, reason="ok")
    failed = make_text_answer(db_session, candidate, "Q2", "f")
    set_job_result(db_session, failed, status=JobStatus.FAILED)
    np = make_text_answer(db_session, candidate, "Q3", "n")
    set_job_result(db_session, np, status=JobStatus.NEEDS_PERSON, needs_person_reason="read")
    sup = job_of(db_session, make_text_answer(db_session, candidate, "Q4", "x"))
    sup.status = JobStatus.SUPERSEDED
    db_session.commit()
    running = job_of(db_session, make_text_answer(db_session, candidate, "Q5", "r"))
    running.status = JobStatus.RUNNING
    running.attempts = 1
    db_session.commit()

    assert claim_next_job(db_session, now=NOW) is None


# --- heartbeat -----------------------------------------------------------------


def test_heartbeat_true_for_own_claim(db_session, queued_job):
    claim = claim_next_job(db_session, now=NOW)
    assert heartbeat(db_session, claim, now=NOW) is True


def test_heartbeat_false_after_supersede(db_session, queued_job):
    claim = claim_next_job(db_session, now=NOW)
    queued_job.status = JobStatus.SUPERSEDED
    db_session.commit()
    assert heartbeat(db_session, claim, now=NOW) is False


# --- write_outcome -------------------------------------------------------------


def scored_outcome():
    return ScoringOutcome(
        status=JobStatus.SCORED,
        suggested_score=3,
        suggested_reason="solid",
        needs_person_reason=None,
        model="gemini-test",
        error=None,
    )


def test_write_outcome_scored_sets_columns(db_session, queued_job):
    claim = claim_next_job(db_session, now=NOW)
    later = NOW + timedelta(seconds=10)
    assert write_outcome(db_session, claim, scored_outcome(), now=later) is True
    job = fresh_status(db_session, queued_job.id)
    assert job.status == JobStatus.SCORED
    assert job.suggested_score == 3
    assert job.suggested_reason == "solid"
    assert job.model == "gemini-test"
    assert job.last_error is None
    assert job.finished_at.replace(tzinfo=UTC) == later
    assert job.updated_at.replace(tzinfo=UTC) == later


def test_write_outcome_failed_clears_scores(db_session, queued_job):
    claim = claim_next_job(db_session, now=NOW)
    outcome = ScoringOutcome(
        status=JobStatus.FAILED,
        suggested_score=None,
        suggested_reason=None,
        needs_person_reason=None,
        model=None,
        error="gave up",
    )
    assert write_outcome(db_session, claim, outcome, now=NOW) is True
    job = fresh_status(db_session, queued_job.id)
    assert job.status == JobStatus.FAILED
    assert job.suggested_score is None
    assert job.suggested_reason is None
    assert job.last_error == "gave up"


def test_write_outcome_false_when_superseded(db_session, queued_job):
    claim = claim_next_job(db_session, now=NOW)
    queued_job.status = JobStatus.SUPERSEDED
    db_session.commit()
    assert write_outcome(db_session, claim, scored_outcome(), now=NOW) is False
    job = fresh_status(db_session, queued_job.id)
    assert job.status == JobStatus.SUPERSEDED
    assert job.suggested_score is None


def test_write_outcome_stale_claim_fenced(db_session, queued_job):
    stale_claim = claim_next_job(db_session, now=NOW)
    # Job gets recovered (lease expiry simulated by direct reset) and re-claimed.
    # The bulk UPDATE left the ORM object stale — expire before rewriting.
    db_session.expire_all()
    queued_job.status = JobStatus.QUEUED
    db_session.commit()
    newer_claim = claim_next_job(db_session, now=NOW + timedelta(seconds=1))
    assert newer_claim.claim_no == stale_claim.claim_no + 1

    assert write_outcome(db_session, stale_claim, scored_outcome(), now=NOW) is False
    job = fresh_status(db_session, queued_job.id)
    assert job.status == JobStatus.RUNNING
    assert job.attempts == newer_claim.claim_no
    assert job.suggested_score is None


# --- requeue_rate_limited -------------------------------------------------------


def test_requeue_rate_limited_refunds_claim(db_session, queued_job):
    claim = claim_next_job(db_session, now=NOW)
    assert requeue_rate_limited(db_session, claim, now=NOW) is True
    job = fresh_status(db_session, queued_job.id)
    assert job.status == JobStatus.QUEUED
    assert job.attempts == 0  # claim refunded


# --- recover_stale_jobs ---------------------------------------------------------


def test_recover_stale_requeues_old_running(db_session, queued_job):
    claim = claim_next_job(db_session, now=NOW)
    later = NOW + LEASE + timedelta(seconds=1)
    n = recover_stale_jobs(db_session, now=later, lease=LEASE, max_claims=3)
    assert n == 1
    job = fresh_status(db_session, queued_job.id)
    assert job.status == JobStatus.QUEUED
    assert job.attempts == claim.claim_no
    assert job.updated_at.replace(tzinfo=UTC) == later


def test_recover_stale_fails_at_max_claims(db_session, queued_job):
    claim_next_job(db_session, now=NOW)
    db_session.expire_all()
    queued_job.attempts = 3
    queued_job.updated_at = NOW  # onupdate would stamp the wall clock instead
    db_session.commit()
    later = NOW + LEASE + timedelta(seconds=1)
    recover_stale_jobs(db_session, now=later, lease=LEASE, max_claims=3)
    job = fresh_status(db_session, queued_job.id)
    assert job.status == JobStatus.FAILED
    assert job.last_error == "worker stopped mid-job"
    assert job.suggested_score is None
    assert job.finished_at.replace(tzinfo=UTC) == later


def test_recover_stale_ignores_fresh_running(db_session, queued_job):
    claim_next_job(db_session, now=NOW)
    recover_stale_jobs(db_session, now=NOW + timedelta(seconds=5), lease=LEASE, max_claims=3)
    job = fresh_status(db_session, queued_job.id)
    assert job.status == JobStatus.RUNNING
