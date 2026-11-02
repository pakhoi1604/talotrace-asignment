from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Answer, Candidate, Question


@dataclass
class Progress:
    total: int
    answered: list[Answer] = field(default_factory=list)
    current_question: Question | None = None
    completed: bool = False


def get_progress(db: Session, candidate: Candidate) -> Progress:
    """Current answers and the next question for a candidate.

    `current_question` is the lowest-position question with no current
    answer; `completed` is True when every question has one.
    """
    questions = db.scalars(select(Question).order_by(Question.position)).all()
    answered = db.scalars(
        select(Answer)
        .where(Answer.candidate_id == candidate.id, Answer.superseded_at.is_(None))
        .order_by(Answer.submitted_at)
    ).all()
    answered_ids = {a.question_id for a in answered}
    current = next((q for q in questions if q.id not in answered_ids), None)
    return Progress(
        total=len(questions),
        answered=list(answered),
        current_question=current,
        completed=current is None,
    )
