"""ORM-free scorer inputs so the worker, tests and live eval agree."""

from dataclasses import dataclass

from app.models.enums import AnswerKind


@dataclass(frozen=True)
class AnswerInput:
    kind: AnswerKind
    text: str | None


@dataclass(frozen=True)
class QuestionInput:
    text: str
    rubric: dict[str, str]  # {"1".."4"}
