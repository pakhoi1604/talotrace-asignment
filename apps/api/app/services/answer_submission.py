import hashlib
import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.time import utcnow
from app.models import Answer, Candidate, Question, ScoringJob
from app.models.enums import AnswerKind, JobStatus
from app.services.interview_progress import get_progress

AUDIO_HASH_PREFIX = b"audio:"


class QuestionNotFound(Exception):
    pass


class OutOfOrder(Exception):
    pass


class InterviewClosed(Exception):
    pass


class ConcurrentSubmission(Exception):
    pass


@dataclass
class AudioMeta:
    path: str
    content_type: str | None
    size: int


@dataclass
class SubmitResult:
    answer: Answer
    created: bool


def text_sha256(text: str) -> str:
    return hashlib.sha256(b"text:" + text.strip().encode()).hexdigest()


def audio_sha256(data: bytes) -> str:
    return hashlib.sha256(AUDIO_HASH_PREFIX + data).hexdigest()


def _load_current_answer(db: Session, candidate_id: str, question_id: str) -> Answer | None:
    # Private hook: the race test patches this to simulate a stale read.
    return db.scalar(
        select(Answer).where(
            Answer.candidate_id == candidate_id,
            Answer.question_id == question_id,
            Answer.superseded_at.is_(None),
        )
    )


def record_answer(
    db: Session,
    candidate: Candidate,
    question_id: str,
    *,
    kind: AnswerKind,
    content_sha256: str,
    text: str | None = None,
    audio: AudioMeta | None = None,
    answer_id: str | None = None,
    submitted_at: datetime | None = None,
    enforce_rules: bool = True,
) -> SubmitResult:
    """Record an answer and queue its scoring job in one transaction.

    Latest wins: a new answer for an already-answered question supersedes
    the current one and its job. Identical content is a no-op replay.
    `enforce_rules=False` (seed only) skips the order/closed checks while
    keeping replay and supersede semantics.
    """
    question = db.get(Question, question_id)
    if question is None:
        raise QuestionNotFound(question_id)

    current = _load_current_answer(db, candidate.id, question_id)
    if current is not None and current.content_sha256 == content_sha256:
        return SubmitResult(current, created=False)

    if enforce_rules:
        progress = get_progress(db, candidate)
        if progress.completed:
            raise InterviewClosed
        answered_ids = {a.question_id for a in progress.answered}
        if question_id not in answered_ids and (
            progress.current_question is None or question_id != progress.current_question.id
        ):
            raise OutOfOrder(question_id)

    now = utcnow()
    if current is not None:
        current.superseded_at = now
        if current.job is not None:
            current.job.status = JobStatus.SUPERSEDED
            current.job.updated_at = now

    answer = Answer(
        id=answer_id or str(uuid.uuid4()),
        candidate_id=candidate.id,
        question_id=question_id,
        kind=kind.value,
        text=text,
        audio_path=audio.path if audio else None,
        audio_content_type=audio.content_type if audio else None,
        audio_size_bytes=audio.size if audio else None,
        content_sha256=content_sha256,
        submitted_at=submitted_at or now,
    )
    db.add(answer)
    db.add(ScoringJob(answer_id=answer.id, status=JobStatus.QUEUED))

    try:
        db.commit()
    except IntegrityError:
        # A concurrent request landed a current answer for the same pair
        # between our read and our write (partial unique index fired).
        db.rollback()
        fresh = _load_current_answer(db, candidate.id, question_id)
        if fresh is not None and fresh.content_sha256 == content_sha256:
            return SubmitResult(fresh, created=False)
        if fresh is not None:
            raise ConcurrentSubmission(question_id) from None
        # Not the unique-index race — a real integrity bug (FK, CHECK, PK).
        raise

    return SubmitResult(answer, created=True)
