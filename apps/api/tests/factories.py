import uuid
from pathlib import Path

from sqlalchemy import select

from app.core.time import utcnow
from app.models import Answer, Candidate, Question, Role, ScoringJob
from app.models.enums import JobStatus


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
    from app.models.enums import AnswerKind
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


def answer_one(db, candidate, question_id: str, text: str | None = None) -> Answer:
    """Answer a single question in-order (first unanswered)."""
    from app.models.enums import AnswerKind
    from app.services.answer_submission import record_answer, text_sha256

    text = text or f"answer {question_id}"
    return record_answer(
        db,
        candidate,
        question_id,
        kind=AnswerKind.TEXT,
        content_sha256=text_sha256(text),
        text=text,
    ).answer


def set_job_result(
    db,
    answer,
    *,
    status,
    score=None,
    reason=None,
    needs_person_reason=None,
):
    """Give an answer's job a worker-style terminal result (no worker involved)."""
    job = answer.job or db.scalar(select(ScoringJob).where(ScoringJob.answer_id == answer.id))
    job.status = status
    job.suggested_score = score
    job.suggested_reason = reason
    job.needs_person_reason = needs_person_reason
    if status in (JobStatus.SCORED, JobStatus.FAILED, JobStatus.NEEDS_PERSON):
        job.attempts = 1
        job.model = "test-model-1"
        job.finished_at = utcnow()
    if status == JobStatus.FAILED:
        job.last_error = "scoring exploded"
    db.commit()
    return job


def add_decision(
    db,
    answer,
    *,
    kind="override",
    score,
    reason=None,
    hr_email="hr@test.local",
):
    from app.models import ScoreDecision

    latest = db.scalar(
        select(ScoreDecision)
        .where(ScoreDecision.answer_id == answer.id)
        .order_by(ScoreDecision.sequence.desc())
        .limit(1)
    )
    decision = ScoreDecision(
        answer_id=answer.id,
        sequence=(latest.sequence + 1) if latest else 1,
        kind=kind,
        score=score,
        reason=reason,
        hr_email=hr_email,
    )
    db.add(decision)
    db.commit()
    return decision


def make_audio_answer(
    db,
    candidate,
    question_id: str,
    upload_dir,
    ext: str = ".m4a",
    content_type: str = "audio/mp4",
) -> Answer:
    """Write a real audio file into upload_dir and attach an audio answer."""
    from app.services.answer_submission import audio_sha256

    payload = b"fake-audio-bytes-" + uuid.uuid4().bytes
    answer_id = str(uuid.uuid4())
    filename = f"{answer_id}{ext}"
    (Path(upload_dir) / filename).write_bytes(payload)
    answer = Answer(
        id=answer_id,
        candidate_id=candidate.id,
        question_id=question_id,
        kind="audio",
        audio_path=filename,
        audio_content_type=content_type,
        audio_size_bytes=len(payload),
        content_sha256=audio_sha256(payload),
        submitted_at=utcnow(),
    )
    db.add(answer)
    db.add(ScoringJob(answer_id=answer.id, status=JobStatus.QUEUED))
    db.commit()
    return answer
