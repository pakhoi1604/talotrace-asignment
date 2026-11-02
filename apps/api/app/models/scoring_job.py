from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.time import utcnow
from app.db.base import Base

if TYPE_CHECKING:
    from app.models.answer import Answer


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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    answer: Mapped["Answer"] = relationship(back_populates="job")
