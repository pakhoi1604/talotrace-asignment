from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.candidate import Candidate
    from app.models.question import Question
    from app.models.scoring_job import ScoringJob


class Answer(Base):
    __tablename__ = "answers"
    __table_args__ = (
        CheckConstraint("kind IN ('text', 'audio')", name="kind_valid"),
        CheckConstraint(
            "(kind = 'text' AND text IS NOT NULL AND audio_path IS NULL) "
            "OR (kind = 'audio' AND audio_path IS NOT NULL)",
            name="content_matches_kind",
        ),
        # Only one current (not superseded) answer per candidate+question.
        Index(
            "uq_answers_current",
            "candidate_id",
            "question_id",
            unique=True,
            sqlite_where=text("superseded_at IS NULL"),
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    candidate_id: Mapped[str] = mapped_column(ForeignKey("candidates.id"))
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"))
    kind: Mapped[str] = mapped_column(String(10))
    text: Mapped[str | None] = mapped_column(Text)
    audio_path: Mapped[str | None] = mapped_column(String(500))
    audio_content_type: Mapped[str | None] = mapped_column(String(100))
    audio_size_bytes: Mapped[int | None] = mapped_column()
    content_sha256: Mapped[str] = mapped_column(String(64))
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    candidate: Mapped["Candidate"] = relationship(back_populates="answers")
    question: Mapped["Question"] = relationship()
    job: Mapped["ScoringJob | None"] = relationship(back_populates="answer", uselist=False)
