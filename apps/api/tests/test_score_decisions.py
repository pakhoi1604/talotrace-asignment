import pytest
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError

from app.core.time import utcnow
from app.models import Answer, ScoreDecision, ScoringJob
from app.models.enums import DecisionKind, JobStatus
from app.services import score_decisions
from app.services.hr_review import final_score
from app.services.score_decisions import (
    AnswerNotFound,
    AnswerSuperseded,
    ConcurrentDecision,
    JobNotFound,
    JobNotRetryable,
    NeedsPersonReview,
    NoSuggestion,
    SuggestionChanged,
    record_decision,
    retry_job,
)

from .factories import (
    answer_one,
    make_audio_answer,
    make_candidate,
    make_role,
    seed_questions,
    set_job_result,
)


@pytest.fixture
def ctx(db_session):
    role = make_role(db_session)
    seed_questions(db_session)
    candidate, _ = make_candidate(db_session, role)
    return candidate


def _decision_count(db, answer_id) -> int:
    return db.scalar(
        select(func.count()).select_from(ScoreDecision).where(ScoreDecision.answer_id == answer_id)
    )


def test_override_creates_first_decision(db_session, ctx):
    answer = answer_one(db_session, ctx, "Q1")
    result = record_decision(
        db_session,
        answer.id,
        kind=DecisionKind.OVERRIDE,
        score=4,
        reason="strong",
        hr_email="hr@test.local",
    )
    assert result.created is True
    assert result.decision.sequence == 1
    assert result.decision.hr_email == "hr@test.local"


def test_identical_repeat_returns_same_row(db_session, ctx):
    answer = answer_one(db_session, ctx, "Q1")
    kwargs = {
        "kind": DecisionKind.OVERRIDE,
        "score": 4,
        "reason": "strong",
        "hr_email": "hr@test.local",
    }
    first = record_decision(db_session, answer.id, **kwargs)
    second = record_decision(db_session, answer.id, **kwargs)
    assert second.created is False
    assert second.decision.id == first.decision.id
    assert _decision_count(db_session, answer.id) == 1


def test_different_override_appends_and_wins(db_session, ctx):
    answer = answer_one(db_session, ctx, "Q1")
    record_decision(
        db_session,
        answer.id,
        kind=DecisionKind.OVERRIDE,
        score=4,
        reason="strong",
        hr_email="hr@test.local",
    )
    result = record_decision(
        db_session,
        answer.id,
        kind=DecisionKind.OVERRIDE,
        score=2,
        reason="on second thought",
        hr_email="hr@test.local",
    )
    assert result.created is True
    assert result.decision.sequence == 2
    assert final_score(db_session.get(Answer, answer.id)) == (2, "hr")


def test_override_on_superseded_and_unknown(db_session, ctx):
    answer = answer_one(db_session, ctx, "Q1")
    answer.superseded_at = utcnow()
    db_session.commit()
    with pytest.raises(AnswerSuperseded):
        record_decision(
            db_session,
            answer.id,
            kind=DecisionKind.OVERRIDE,
            score=4,
            reason="x",
            hr_email="hr@test.local",
        )
    with pytest.raises(AnswerNotFound):
        record_decision(
            db_session,
            "missing",
            kind=DecisionKind.OVERRIDE,
            score=4,
            reason="x",
            hr_email="hr@test.local",
        )


def test_service_validates_score_and_reason(db_session, ctx):
    answer = answer_one(db_session, ctx, "Q1")
    for score, reason in ((5, "ok"), (0, "ok"), (3, "   "), (3, "x" * 2001)):
        with pytest.raises(ValueError):
            record_decision(
                db_session,
                answer.id,
                kind=DecisionKind.OVERRIDE,
                score=score,
                reason=reason,
                hr_email="hr@test.local",
            )


def test_override_allowed_for_any_job_status(db_session, ctx, upload_dir):
    queued = answer_one(db_session, ctx, "Q1")
    failed = answer_one(db_session, ctx, "Q2")
    set_job_result(db_session, failed, status=JobStatus.FAILED)
    flag = answer_one(db_session, ctx, "Q3")
    set_job_result(
        db_session,
        flag,
        status=JobStatus.NEEDS_PERSON,
        score=2,
        reason="maybe",
        needs_person_reason="unclear",
    )
    audio = make_audio_answer(db_session, ctx, "Q4", upload_dir)

    for answer in (queued, failed, flag, audio):
        result = record_decision(
            db_session,
            answer.id,
            kind=DecisionKind.OVERRIDE,
            score=4,
            reason="hr decides",
            hr_email="hr@test.local",
        )
        assert result.created is True


def test_accept_requires_matching_scored_suggestion(db_session, ctx):
    answer = answer_one(db_session, ctx, "Q1")
    set_job_result(db_session, answer, status=JobStatus.SCORED, score=3, reason="good")

    result = record_decision(
        db_session,
        answer.id,
        kind=DecisionKind.ACCEPT,
        score=3,
        reason=None,
        hr_email="hr@test.local",
    )
    assert result.created is True
    assert result.decision.reason is None

    with pytest.raises(SuggestionChanged):
        record_decision(
            db_session,
            answer.id,
            kind=DecisionKind.ACCEPT,
            score=2,
            reason=None,
            hr_email="hr@test.local",
        )


def test_accept_rejected_without_suggestion(db_session, ctx):
    queued = answer_one(db_session, ctx, "Q1")
    failed = answer_one(db_session, ctx, "Q2")
    set_job_result(db_session, failed, status=JobStatus.FAILED)
    flag = answer_one(db_session, ctx, "Q3")
    set_job_result(
        db_session,
        flag,
        status=JobStatus.NEEDS_PERSON,
        score=2,
        reason="maybe",
        needs_person_reason="unclear",
    )

    for answer in (queued, failed):
        with pytest.raises(NoSuggestion):
            record_decision(
                db_session,
                answer.id,
                kind=DecisionKind.ACCEPT,
                score=3,
                reason=None,
                hr_email="hr@test.local",
            )
    with pytest.raises(NeedsPersonReview):
        record_decision(
            db_session,
            flag.id,
            kind=DecisionKind.ACCEPT,
            score=2,
            reason=None,
            hr_email="hr@test.local",
        )


def test_decision_race_identical_repeat_and_conflict(db_session, session_factory, ctx, monkeypatch):
    answer = answer_one(db_session, ctx, "Q1")

    # A second session lands sequence 1 before our stale read catches up.
    other = session_factory()
    record_decision(
        other,
        answer.id,
        kind=DecisionKind.OVERRIDE,
        score=4,
        reason="from another session",
        hr_email="hr@test.local",
    )

    monkeypatch.setattr(score_decisions, "_latest_decision", lambda db, aid: None)

    same = record_decision(
        db_session,
        answer.id,
        kind=DecisionKind.OVERRIDE,
        score=4,
        reason="from another session",
        hr_email="hr@test.local",
    )
    assert same.created is False
    assert _decision_count(db_session, answer.id) == 1

    with pytest.raises(ConcurrentDecision):
        record_decision(
            db_session,
            answer.id,
            kind=DecisionKind.OVERRIDE,
            score=1,
            reason="different",
            hr_email="hr@test.local",
        )
    other.close()


def test_supersede_during_decision_is_rejected(db_session, session_factory, ctx):
    answer = answer_one(db_session, ctx, "Q1")
    db_session.get(Answer, answer.id)  # prime this session's identity map

    other = session_factory()
    other.execute(update(Answer).where(Answer.id == answer.id).values(superseded_at=utcnow()))
    other.commit()
    other.close()

    with pytest.raises(AnswerSuperseded):
        record_decision(
            db_session,
            answer.id,
            kind=DecisionKind.OVERRIDE,
            score=4,
            reason="x",
            hr_email="hr@test.local",
        )
    assert _decision_count(db_session, answer.id) == 0


def test_accept_when_suggestion_vanished(db_session, session_factory, ctx):
    answer = answer_one(db_session, ctx, "Q1")
    set_job_result(db_session, answer, status=JobStatus.SCORED, score=3, reason="good")
    assert answer.job is not None  # prime the stale read in this session

    other = session_factory()
    other.execute(
        update(ScoringJob)
        .where(ScoringJob.id == answer.job.id)
        .values(status=JobStatus.QUEUED, suggested_score=None, suggested_reason=None)
    )
    other.commit()
    other.close()

    with pytest.raises((NoSuggestion, SuggestionChanged)):
        record_decision(
            db_session,
            answer.id,
            kind=DecisionKind.ACCEPT,
            score=3,
            reason=None,
            hr_email="hr@test.local",
        )
    assert _decision_count(db_session, answer.id) == 0


def test_unrelated_integrity_error_reraises(db_session, session_factory, ctx):
    answer = answer_one(db_session, ctx, "Q1")
    assert answer.job is not None  # prime

    # Break the FK: remove the answer (and its job) in another session.
    other = session_factory()
    victim = other.get(Answer, answer.id)
    other.delete(victim.job)
    other.delete(victim)
    other.commit()
    other.close()

    with pytest.raises(IntegrityError):
        record_decision(
            db_session,
            answer.id,
            kind=DecisionKind.OVERRIDE,
            score=4,
            reason="x",
            hr_email="hr@test.local",
        )


def test_retry_failed_job(db_session, ctx):
    answer = answer_one(db_session, ctx, "Q1")
    job = set_job_result(db_session, answer, status=JobStatus.FAILED)

    result = retry_job(db_session, job.id)
    assert result.changed is True
    assert result.job.status == JobStatus.QUEUED
    assert result.job.attempts == 0
    assert result.job.last_error is None
    assert result.job.suggested_score is None
    assert result.job.suggested_reason is None
    assert result.job.needs_person_reason is None


def test_retry_noop_and_non_retryable(db_session, ctx):
    answers = [answer_one(db_session, ctx, f"Q{i}") for i in range(1, 6)]
    set_job_result(db_session, answers[1], status=JobStatus.SCORED, score=3, reason="ok")
    set_job_result(db_session, answers[2], status=JobStatus.RUNNING)
    set_job_result(
        db_session,
        answers[3],
        status=JobStatus.NEEDS_PERSON,
        needs_person_reason="unclear",
    )
    set_job_result(db_session, answers[4], status=JobStatus.SUPERSEDED)

    queued = retry_job(db_session, answers[0].job.id)
    assert queued.changed is False

    for answer in answers[1:]:
        with pytest.raises(JobNotRetryable):
            retry_job(db_session, answer.job.id)

    with pytest.raises(JobNotFound):
        retry_job(db_session, 99999)


def test_retry_double_click_not_stale(db_session, session_factory, ctx):
    answer = answer_one(db_session, ctx, "Q1")
    job = set_job_result(db_session, answer, status=JobStatus.FAILED)

    other = session_factory()
    first = retry_job(other, job.id)
    assert first.changed is True

    second = retry_job(db_session, job.id)
    assert second.changed is False
    assert second.job.status == JobStatus.QUEUED
    other.close()
