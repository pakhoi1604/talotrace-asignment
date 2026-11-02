import pytest
from sqlalchemy.exc import IntegrityError

from app.core.time import utcnow
from app.models import Answer, Candidate, Question, Role, ScoringJob

from .factories import make_candidate, make_role, seed_questions


def _answer(candidate_id, question_id, **kwargs):
    defaults = {
        "id": "ans-1",
        "kind": "text",
        "text": "hello",
        "content_sha256": "x" * 64,
        "submitted_at": utcnow(),
    }
    defaults.update(kwargs)
    return Answer(candidate_id=candidate_id, question_id=question_id, **defaults)


def test_two_current_answers_same_pair_rejected(db_session):
    role = make_role(db_session)
    candidate, _ = make_candidate(db_session, role, with_token=False)
    seed_questions(db_session)
    db_session.add(_answer(candidate.id, "Q1"))
    db_session.commit()

    db_session.add(_answer(candidate.id, "Q1", id="ans-2"))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_superseded_plus_current_answer_allowed(db_session):
    role = make_role(db_session)
    candidate, _ = make_candidate(db_session, role, with_token=False)
    seed_questions(db_session)
    db_session.add(_answer(candidate.id, "Q1", superseded_at=utcnow()))
    db_session.add(_answer(candidate.id, "Q1", id="ans-2"))
    db_session.commit()

    assert db_session.query(Answer).count() == 2


def test_second_job_for_same_answer_rejected(db_session):
    role = make_role(db_session)
    candidate, _ = make_candidate(db_session, role, with_token=False)
    seed_questions(db_session)
    answer = _answer(candidate.id, "Q1")
    db_session.add(answer)
    db_session.commit()
    db_session.add(ScoringJob(answer_id=answer.id))
    db_session.commit()

    db_session.add(ScoringJob(answer_id=answer.id))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_invalid_answer_kind_rejected(db_session):
    role = make_role(db_session)
    candidate, _ = make_candidate(db_session, role, with_token=False)
    seed_questions(db_session)
    db_session.add(_answer(candidate.id, "Q1", kind="video"))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_invalid_job_status_rejected(db_session):
    role = make_role(db_session)
    candidate, _ = make_candidate(db_session, role, with_token=False)
    seed_questions(db_session)
    answer = _answer(candidate.id, "Q1")
    db_session.add(answer)
    db_session.commit()
    db_session.add(ScoringJob(answer_id=answer.id, status="bogus"))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_text_kind_without_text_rejected(db_session):
    role = make_role(db_session)
    candidate, _ = make_candidate(db_session, role, with_token=False)
    seed_questions(db_session)
    db_session.add(_answer(candidate.id, "Q1", text=None))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_tables_created(engine, db_session):
    # sanity: the five plan tables exist and accept a minimal graph
    role = Role(title="X Engineer")
    db_session.add(role)
    db_session.commit()
    db_session.add(Candidate(id="C9000", name="N", email="n@example.com", role_id=role.id))
    db_session.commit()
    assert db_session.get(Question, "Q1") is None  # no seed data here
