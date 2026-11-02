from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.time import utcnow
from app.db.base import Base

if TYPE_CHECKING:
    from app.models.answer import Answer


class ScoreDecision(Base):
    """Append-only HR decision. The newest sequence per answer counts."""

    __tablename__ = "score_decisions"
    __table_args__ = (
        UniqueConstraint("answer_id", "sequence", name="uq_score_decisions_answer_seq"),
        CheckConstraint("kind IN ('override', 'accept')", name="kind_valid"),
        CheckConstraint("score BETWEEN 1 AND 4", name="score_range"),
        CheckConstraint("kind <> 'override' OR reason IS NOT NULL", name="override_needs_reason"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    answer_id: Mapped[str] = mapped_column(ForeignKey("answers.id"))
    sequence: Mapped[int] = mapped_column()
    kind: Mapped[str] = mapped_column(String(10))
    score: Mapped[int] = mapped_column()
    reason: Mapped[str | None] = mapped_column(Text)
    hr_email: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    answer: Mapped["Answer"] = relationship(back_populates="decisions")
