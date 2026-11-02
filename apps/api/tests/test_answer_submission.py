import pytest

import app.services.answer_submission as submission
from app.core.time import utcnow
from app.models import Answer, ScoringJob
from app.models.enums import AnswerKind, JobStatus
from app.services.answer_submission import (
    AudioMeta,
    ConcurrentSubmission,
    InterviewClosed,
    OutOfOrder,
    QuestionNotFound,
    record_answer,
    text_sha256,
)
from app.services.interview_progress import get_progress

from .factories import answer_all, make_candidate, make_role, seed_questions


def _setup(db):
    role = make_role(db)
    candidate, _ = make_candidate(db, role)
    seed_questions(db)
    return candidate


def _submit_text(db, candidate, question_id, text, **kwargs):
    return record_answer(
        db,
        candidate,
        question_id,
        kind=AnswerKind.TEXT,
        content_sha256=text_sha256(text),
        text=text,
        **kwargs,
    )


def _current_answers(db, candidate):
    return (
        db.query(Answer)
        .filter(Answer.candidate_id == candidate.id, Answer.superseded_at.is_(None))
        .all()
    )


def test_first_submit_creates_answer_and_queued_job(db_session):
    candidate = _setup(db_session)

    result = _submit_text(db_session, candidate, "Q1", "hello")

    assert result.created is True
    answers = db_session.query(Answer).all()
    jobs = db_session.query(ScoringJob).all()
    assert len(answers) == 1 and answers[0].id == result.answer.id
    assert len(jobs) == 1
    assert jobs[0].answer_id == result.answer.id
    assert jobs[0].status == JobStatus.QUEUED


def test_identical_replay_is_noop(db_session):
    candidate = _setup(db_session)
    first = _submit_text(db_session, candidate, "Q1", "hello")

    replay = _submit_text(db_session, candidate, "Q1", " hello  ")

    assert replay.created is False
    assert replay.answer.id == first.answer.id
    assert db_session.query(Answer).count() == 1
    assert db_session.query(ScoringJob).count() == 1


def test_different_content_supersedes_current(db_session):
    candidate = _setup(db_session)
    first = _submit_text(db_session, candidate, "Q1", "v1")

    second = _submit_text(db_session, candidate, "Q1", "v2")

    assert second.created is True
    db_session.refresh(first.answer)
    assert first.answer.superseded_at is not None
    assert first.answer.job.status == JobStatus.SUPERSEDED
    current = _current_answers(db_session, candidate)
    assert len(current) == 1 and current[0].id == second.answer.id
    assert second.answer.job.status == JobStatus.QUEUED


def test_unanswered_non_current_question_out_of_order(db_session):
    candidate = _setup(db_session)

    with pytest.raises(OutOfOrder):
        _submit_text(db_session, candidate, "Q3", "skip ahead")

    assert db_session.query(Answer).count() == 0


def test_replacing_answered_question_while_incomplete_allowed(db_session):
    candidate = _setup(db_session)
    _submit_text(db_session, candidate, "Q1", "q1 v1")

    result = _submit_text(db_session, candidate, "Q1", "q1 v2")
    assert result.created is True
    # still allowed to answer Q2 afterwards
    assert _submit_text(db_session, candidate, "Q2", "q2").created is True


def test_closed_interview_rejects_new_content_allows_replay(db_session):
    candidate = _setup(db_session)
    answer_all(db_session, candidate)

    with pytest.raises(InterviewClosed):
        _submit_text(db_session, candidate, "Q1", "changed content")

    replay = _submit_text(db_session, candidate, "Q1", "answer 1")
    assert replay.created is False


def test_unknown_question_raises_not_found(db_session):
    candidate = _setup(db_session)

    with pytest.raises(QuestionNotFound):
        _submit_text(db_session, candidate, "Q9", "hi")


def test_enforce_rules_false_stores_explicit_id_and_timestamp(db_session):
    candidate = _setup(db_session)
    when = utcnow()

    result = record_answer(
        db_session,
        candidate,
        "Q4",
        kind=AnswerKind.TEXT,
        content_sha256=text_sha256("out of band"),
        text="out of band",
        answer_id="pack-A1",
        submitted_at=when,
        enforce_rules=False,
    )

    assert result.created is True
    assert result.answer.id == "pack-A1"
    assert result.answer.submitted_at == when
    assert result.answer.job.status == JobStatus.QUEUED


def test_audio_answer_stores_metadata(db_session):
    candidate = _setup(db_session)

    result = record_answer(
        db_session,
        candidate,
        "Q1",
        kind=AnswerKind.AUDIO,
        content_sha256="f" * 64,
        audio=AudioMeta(path="a1.m4a", content_type="audio/mp4", size=123),
    )

    assert result.answer.kind == AnswerKind.AUDIO
    assert result.answer.audio_path == "a1.m4a"
    assert result.answer.audio_size_bytes == 123


def test_concurrent_identical_submission_replays(db_session, session_factory, monkeypatch):
    candidate = _setup(db_session)
    _commit_competing_answer(session_factory, candidate, "Q1", "same text")

    _stale_read_once(monkeypatch)
    result = _submit_text(db_session, candidate, "Q1", " same text ")

    assert result.created is False
    assert len(_current_answers(db_session, candidate)) == 1


def test_concurrent_different_submission_raises(db_session, session_factory, monkeypatch):
    candidate = _setup(db_session)
    _commit_competing_answer(session_factory, candidate, "Q1", "winner text")

    _stale_read_once(monkeypatch)
    with pytest.raises(ConcurrentSubmission):
        _submit_text(db_session, candidate, "Q1", "loser text")

    assert len(_current_answers(db_session, candidate)) == 1


def _commit_competing_answer(session_factory, candidate, question_id, text):
    """A second session lands a current answer first, as in a double-click race."""
    db2 = session_factory()
    db2.add(
        Answer(
            id="competing-answer",
            candidate_id=candidate.id,
            question_id=question_id,
            kind=AnswerKind.TEXT,
            text=text,
            content_sha256=text_sha256(text),
            submitted_at=utcnow(),
        )
    )
    db2.commit()
    db2.close()


def _stale_read_once(monkeypatch):
    """Simulate a stale read: first lookup misses, later lookups see the real row."""
    original = submission._load_current_answer
    calls = {"n": 0}

    def stale(db, candidate_id, question_id):
        calls["n"] += 1
        if calls["n"] == 1:
            return None
        return original(db, candidate_id, question_id)

    monkeypatch.setattr(submission, "_load_current_answer", stale)


def test_progress_advances_and_counts_current_answers(db_session):
    candidate = _setup(db_session)

    progress = get_progress(db_session, candidate)
    assert progress.total == 6
    assert progress.current_question.id == "Q1"
    assert progress.answered == []
    assert progress.completed is False

    _submit_text(db_session, candidate, "Q1", "a1")
    record_answer(
        db_session,
        candidate,
        "Q3",
        kind=AnswerKind.TEXT,
        content_sha256=text_sha256("a3"),
        text="a3",
        enforce_rules=False,
    )

    progress = get_progress(db_session, candidate)
    assert progress.current_question.id == "Q2"
    assert len(progress.answered) == 2
    assert progress.completed is False
