"""DB queue operations for the worker.

Every write is a Core UPDATE with its own commit — no transaction is ever held
open across an LLM call. The fence (id + status='running' + attempts=claim_no)
makes superseded and re-claimed jobs discard a late result, and makes a stale
worker's write a no-op. `attempts` is the number of claims (runs); the claim
number is the fence token. Bulk UPDATEs bypass ORM events — safe because
ScoringOutcome already ran validate_job_result and every outcome writes all
score columns; claim/heartbeat/recover/requeue only move between
queued/running/failed, which carry no scores.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.enums import JobStatus
from app.models.scoring_job import ScoringJob
from app.scoring.score_answer import ScoringOutcome


@dataclass(frozen=True)
class Claim:
    job_id: int
    claim_no: int  # attempts after the claim — the fence token


def _next_queued_id(db: Session) -> int | None:
    """Private hook: the race test patches this to simulate a stale read."""
    return db.scalar(
        select(ScoringJob.id)
        .where(ScoringJob.status == JobStatus.QUEUED)
        .order_by(ScoringJob.created_at, ScoringJob.id)
        .limit(1)
    )


def claim_next_job(db: Session, *, now: datetime) -> Claim | None:
    while (job_id := _next_queued_id(db)) is not None:
        res = db.execute(
            update(ScoringJob)
            .where(ScoringJob.id == job_id, ScoringJob.status == JobStatus.QUEUED)
            .values(
                status=JobStatus.RUNNING,
                attempts=ScoringJob.attempts + 1,
                updated_at=now,
            )
            .execution_options(synchronize_session=False)
        )
        db.commit()
        if res.rowcount == 1:
            claim_no = db.scalar(select(ScoringJob.attempts).where(ScoringJob.id == job_id))
            return Claim(job_id, claim_no)
        # Lost the race: another worker claimed it first. Try the next job.
    return None


def _fence(claim: Claim):
    return (
        ScoringJob.id == claim.job_id,
        ScoringJob.status == JobStatus.RUNNING,
        ScoringJob.attempts == claim.claim_no,
    )


def heartbeat(db: Session, claim: Claim, *, now: datetime) -> bool:
    """Prove the job is still ours before spending an LLM call."""
    res = db.execute(
        update(ScoringJob)
        .where(*_fence(claim))
        .values(updated_at=now)
        .execution_options(synchronize_session=False)
    )
    db.commit()
    return res.rowcount == 1


def write_outcome(db: Session, claim: Claim, outcome: ScoringOutcome, *, now: datetime) -> bool:
    """Fenced write of a terminal result. False = no longer ours (discarded)."""
    res = db.execute(
        update(ScoringJob)
        .where(*_fence(claim))
        .values(
            status=outcome.status,
            suggested_score=outcome.suggested_score,
            suggested_reason=outcome.suggested_reason,
            needs_person_reason=outcome.needs_person_reason,
            model=outcome.model,
            last_error=outcome.error,
            finished_at=now,
            updated_at=now,
        )
        .execution_options(synchronize_session=False)
    )
    db.commit()
    return res.rowcount == 1


def requeue_rate_limited(db: Session, claim: Claim, *, now: datetime) -> bool:
    """429: back to queued with the claim refunded — never counts toward failed."""
    res = db.execute(
        update(ScoringJob)
        .where(*_fence(claim))
        .values(
            status=JobStatus.QUEUED,
            attempts=ScoringJob.attempts - 1,
            updated_at=now,
        )
        .execution_options(synchronize_session=False)
    )
    db.commit()
    return res.rowcount == 1


def recover_stale_jobs(db: Session, *, now: datetime, lease: timedelta, max_claims: int) -> int:
    """Requeue `running` jobs whose lease expired; fail them at max claims."""
    cutoff = now - lease
    stale = (ScoringJob.status == JobStatus.RUNNING, ScoringJob.updated_at < cutoff)
    failed = db.execute(
        update(ScoringJob)
        .where(*stale, ScoringJob.attempts >= max_claims)
        .values(
            status=JobStatus.FAILED,
            last_error="worker stopped mid-job",
            finished_at=now,
            updated_at=now,
        )
        .execution_options(synchronize_session=False)
    )
    requeued = db.execute(
        update(ScoringJob)
        .where(*stale, ScoringJob.attempts < max_claims)
        .values(status=JobStatus.QUEUED, updated_at=now)
        .execution_options(synchronize_session=False)
    )
    db.commit()
    return failed.rowcount + requeued.rowcount
