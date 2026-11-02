"""HR decisions (append-only) and failed-job retry. No FastAPI imports."""

from dataclasses import dataclass

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.time import utcnow
from app.models import Answer, ScoreDecision, ScoringJob
from app.models.enums import DecisionKind, JobStatus


class AnswerNotFound(Exception):
    pass


class AnswerSuperseded(Exception):
    pass


class NoSuggestion(Exception):
    pass


class NeedsPersonReview(Exception):
    pass


class SuggestionChanged(Exception):
    pass


class ConcurrentDecision(Exception):
    pass


class JobNotFound(Exception):
    pass


class JobNotRetryable(Exception):
    pass


@dataclass
class DecisionResult:
    decision: ScoreDecision
    created: bool


@dataclass
class RetryResult:
    job: ScoringJob
    changed: bool


def _load_answer(db: Session, answer_id: str) -> Answer | None:
    # Private hook: the supersede-race test relies on a stale read through
    # this function (and patches it by name).
    return db.get(Answer, answer_id)


def _latest_decision(db: Session, answer_id: str) -> ScoreDecision | None:
    # Private hook: the decision-race test patches this by name.
    return db.scalar(
        select(ScoreDecision)
        .where(ScoreDecision.answer_id == answer_id)
        .order_by(ScoreDecision.sequence.desc())
        .limit(1)
    )


def _check_accept(job: ScoringJob | None, score: int) -> None:
    if job is not None and job.status == JobStatus.NEEDS_PERSON:
        # A flagged score needs an override with a reason, not an accept.
        raise NeedsPersonReview
    if job is None or job.status != JobStatus.SCORED:
        raise NoSuggestion
    if job.suggested_score != score:
        raise SuggestionChanged


def _same(decision: ScoreDecision, *, kind, score, reason, hr_email) -> bool:
    return (
        decision.kind == str(kind)
        and decision.score == score
        and decision.reason == reason
        and decision.hr_email == hr_email
    )


def record_decision(
    db: Session,
    answer_id: str,
    *,
    kind: DecisionKind,
    score: int,
    reason: str | None,
    hr_email: str,
) -> DecisionResult:
    """Append a decision. Identical repeat of the newest → same row, not a dup.

    The supersede/suggestion checks run once on the (possibly stale) read and
    again inside the write transaction, closing the check-then-act gap
    against a candidate resubmission or a retry that clears the suggestion.
    """
    if not (1 <= score <= 4):
        raise ValueError("score must be between 1 and 4")
    if kind == DecisionKind.ACCEPT:
        reason = None
    else:
        reason = reason.strip() if reason else ""
        if not reason:
            raise ValueError("reason must not be blank")
        if len(reason) > 2000:
            raise ValueError("reason must be at most 2000 characters")

    answer = _load_answer(db, answer_id)
    if answer is None:
        raise AnswerNotFound
    if answer.superseded_at is not None:
        raise AnswerSuperseded
    if kind == DecisionKind.ACCEPT:
        _check_accept(answer.job, score)

    latest = _latest_decision(db, answer_id)
    if latest is not None and _same(
        latest, kind=kind, score=score, reason=reason, hr_email=hr_email
    ):
        return DecisionResult(latest, False)

    sequence = (latest.sequence if latest else 0) + 1
    decision = ScoreDecision(
        answer_id=answer_id,
        sequence=sequence,
        kind=str(kind),
        score=score,
        reason=reason,
        hr_email=hr_email,
    )
    db.add(decision)
    try:
        # The INSERT opens pysqlite's write transaction; from here to commit
        # no other writer can commit, so the fresh re-reads below are final.
        db.flush()
        fresh_answer = db.scalar(
            select(Answer).where(Answer.id == answer_id).execution_options(populate_existing=True)
        )
        if fresh_answer is None or fresh_answer.superseded_at is not None:
            raise AnswerSuperseded
        if kind == DecisionKind.ACCEPT:
            fresh_job = db.scalar(
                select(ScoringJob)
                .where(ScoringJob.answer_id == answer_id)
                .execution_options(populate_existing=True)
            )
            _check_accept(fresh_job, score)
        db.commit()
    except IntegrityError:
        # UNIQUE(answer_id, sequence) fired — someone else decided first.
        db.rollback()
        row = db.scalar(
            select(ScoreDecision).where(
                ScoreDecision.answer_id == answer_id,
                ScoreDecision.sequence == sequence,
            )
        )
        if row is not None:
            if _same(row, kind=kind, score=score, reason=reason, hr_email=hr_email):
                return DecisionResult(row, False)
            raise ConcurrentDecision from None
        # Not the sequence race — a real integrity bug (FK, CHECK, PK).
        raise
    except Exception:
        db.rollback()
        raise
    return DecisionResult(decision, True)


def retry_job(db: Session, job_id: int) -> RetryResult:
    """Re-queue a failed job. Conditional UPDATE: a double click is a no-op.

    The bulk UPDATE bypasses ORM events, so it clears every score column in
    the same statement to satisfy the job-result invariant.
    """
    job = db.get(ScoringJob, job_id)
    if job is None:
        raise JobNotFound
    res = db.execute(
        update(ScoringJob)
        .where(ScoringJob.id == job_id, ScoringJob.status == JobStatus.FAILED)
        .values(
            status=JobStatus.QUEUED,
            attempts=0,
            last_error=None,
            suggested_score=None,
            suggested_reason=None,
            needs_person_reason=None,
            finished_at=None,
            updated_at=utcnow(),
        )
        .execution_options(synchronize_session=False)
    )
    db.commit()
    # expire_on_commit=False sessions keep stale rows — refresh before reading.
    db.refresh(job)
    if res.rowcount == 1:
        return RetryResult(job, True)
    if job.status == JobStatus.QUEUED:
        return RetryResult(job, False)
    raise JobNotRetryable
