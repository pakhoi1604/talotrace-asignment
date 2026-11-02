from datetime import datetime
from typing import Literal

from pydantic import BaseModel, field_validator


class TextAnswerIn(BaseModel):
    text: str

    @field_validator("text")
    @classmethod
    def _validate_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        if len(value) > 10_000:
            raise ValueError("must be at most 10000 characters")
        return value


class CurrentQuestion(BaseModel):
    id: str
    position: int
    text: str


class AnsweredItem(BaseModel):
    question_id: str
    position: int
    kind: Literal["text", "audio"]
    received_at: datetime


class InterviewView(BaseModel):
    candidate_name: str
    role: str
    total_questions: int
    answered_count: int
    completed: bool
    current_question: CurrentQuestion | None
    answered: list[AnsweredItem]


class AnswerReceipt(BaseModel):
    answer_id: str
    question_id: str
    kind: Literal["text", "audio"]
    received_at: datetime
    status: Literal["received"] = "received"
