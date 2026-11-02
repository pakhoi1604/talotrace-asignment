from sqlalchemy import JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[str] = mapped_column(String(4), primary_key=True)
    position: Mapped[int] = mapped_column(unique=True)
    text: Mapped[str] = mapped_column(Text)
    rubric: Mapped[dict] = mapped_column(JSON)
