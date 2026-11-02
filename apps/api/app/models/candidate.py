from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.time import utcnow
from app.db.base import Base

if TYPE_CHECKING:
    from app.models.answer import Answer
    from app.models.role import Role


class Candidate(Base):
    __tablename__ = "candidates"

    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(200))
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"), index=True)
    access_token_hash: Mapped[str | None] = mapped_column(String(64), unique=True)
    token_issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    role: Mapped["Role"] = relationship(back_populates="candidates")
    answers: Mapped[list["Answer"]] = relationship(back_populates="candidate")
