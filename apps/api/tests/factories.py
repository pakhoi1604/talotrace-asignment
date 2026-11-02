from app.models import Candidate, Question, Role
from app.models.enums import AnswerKind


def make_role(db, title: str = "Backend Engineer") -> Role:
    role = Role(title=title)
    db.add(role)
    db.commit()
    return role


def seed_questions(db) -> list[Question]:
    questions = [
        Question(
            id=f"Q{i}",
            position=i,
            text=f"Question {i}?",
            rubric={str(n): f"level {n}" for n in range(1, 5)},
        )
        for i in range(1, 7)
    ]
    db.add_all(questions)
    db.commit()
    return questions


def make_candidate(db, role, id: str = "C0001", with_token: bool = True):
    candidate = Candidate(
        id=id, name=f"Candidate {id}", email=f"{id.lower()}@example.com", role_id=role.id
    )
    db.add(candidate)
    db.commit()
    if not with_token:
        return candidate, None
    from app.services.candidate_access import issue_token

    token = issue_token(db, candidate)
    db.commit()
    return candidate, token


def answer_all(db, candidate) -> list:
    from app.services.answer_submission import record_answer, text_sha256

    answers = []
    for i in range(1, 7):
        text = f"answer {i}"
        result = record_answer(
            db,
            candidate,
            f"Q{i}",
            kind=AnswerKind.TEXT,
            content_sha256=text_sha256(text),
            text=text,
        )
        answers.append(result.answer)
    return answers
