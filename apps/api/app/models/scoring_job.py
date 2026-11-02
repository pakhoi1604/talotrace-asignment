from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, event
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship, validates

from app.core.time import utcnow
from app.db.base import Base
from app.models.enums import JobStatus

if TYPE_CHECKING:
    from app.models.answer import Answer


def validate_job_result(status, suggested_score, suggested_reason, needs_person_reason) -> None:
    """The one rule set for job result columns, shared with the worker plan.

    Raises ValueError when the combination is impossible:
    - suggested_score is always None or 1..4
    - scored needs a score and a reason
    - queued/running/failed never carry a score
    - needs_person needs its reason
    - superseded keeps whatever it had
    """
    if suggested_score is not None and not (1 <= suggested_score <= 4):
        raise ValueError("suggested_score must be between 1 and 4")
    if status == JobStatus.SCORED:
        if suggested_score is None or suggested_reason is None:
            raise ValueError("scored job needs suggested_score and suggested_reason")
    elif status in (JobStatus.QUEUED, JobStatus.RUNNING, JobStatus.FAILED):
        if suggested_score is not None:
            raise ValueError(f"{status} job must not carry a suggested_score")
    elif status == JobStatus.NEEDS_PERSON and needs_person_reason is None:
        raise ValueError("needs_person job needs needs_person_reason")


class ScoringJob(Base):
    __tablename__ = "scoring_jobs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'running', 'scored', 'failed', 'needs_person', 'superseded')",
            name="status_valid",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    answer_id: Mapped[str] = mapped_column(ForeignKey("answers.id"), unique=True)
    status: Mapped[str] = mapped_column(String(20), default="queued")
    attempts: Mapped[int] = mapped_column(default=0)
    last_error: Mapped[str | None] = mapped_column(Text)
    suggested_score: Mapped[int | None] = mapped_column()
    suggested_reason: Mapped[str | None] = mapped_column(Text)
    needs_person_reason: Mapped[str | None] = mapped_column(Text)
    model: Mapped[str | None] = mapped_column(String(100))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    answer: Mapped["Answer"] = relationship(back_populates="job")

    @validates("suggested_score")
    def _validate_suggested_score(self, _key, value):
        if value is not None and not (1 <= value <= 4):
            raise ValueError("suggested_score must be between 1 and 4")
        return value

    def check_result_invariants(self) -> None:
        try:
            validate_job_result(
                self.status,
                self.suggested_score,
                self.suggested_reason,
                self.needs_person_reason,
            )
        except ValueError as exc:
            raise ValueError(f"scoring job {self.id}: {exc}") from exc


# Result invariants live in the ORM, not DB CHECKs (autogenerate can't add
# CHECKs to an existing table and hand-written migrations are banned).
# Bulk UPDATEs bypass this — the retry path clears score columns in the same
# statement and the worker contract validates before writing.
@event.listens_for(Session, "before_flush")
def _enforce_job_result_invariants(session, _flush_context, _instances):
    for obj in session.new.union(session.dirty):
        if isinstance(obj, ScoringJob):
            obj.check_result_invariants()
