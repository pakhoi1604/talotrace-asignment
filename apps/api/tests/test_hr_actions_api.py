import pytest

from app.models.enums import JobStatus

from .factories import (
    answer_one,
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


def test_override_creates_and_repeats(hr_client, ctx, db_session):
    answer = answer_one(db_session, ctx, "Q1")
    body = {"score": 4, "reason": "clearly strong"}
    resp = hr_client.post(f"/api/hr/answers/{answer.id}/override", json=body)
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["answer_id"] == answer.id
    assert data["kind"] == "override"
    assert data["score"] == 4
    assert data["reason"] == "clearly strong"
    assert data["hr_email"] == "hr@test.local"
    assert data["created_at"].endswith(("Z", "+00:00"))

    again = hr_client.post(f"/api/hr/answers/{answer.id}/override", json=body)
    assert again.status_code == 200
    assert again.json()["id"] == data["id"]


def test_override_validation(hr_client, ctx, db_session):
    answer = answer_one(db_session, ctx, "Q1")
    url = f"/api/hr/answers/{answer.id}/override"

    for bad in ({"score": 0, "reason": "x"}, {"score": 5, "reason": "x"}, {"reason": "x"}):
        resp = hr_client.post(url, json=bad)
        assert resp.status_code == 422, bad
        assert resp.json()["detail"].startswith("score:"), resp.json()

    resp = hr_client.post(url, json={"score": 3, "reason": "   "})
    assert resp.status_code == 422
    assert resp.json()["detail"] == "reason: must not be blank"

    resp = hr_client.post(url, json={"score": 3, "reason": "x" * 2001})
    assert resp.status_code == 422
    assert resp.json()["detail"] == "reason: must be at most 2000 characters"


def test_override_requires_json(hr_client, ctx, db_session):
    answer = answer_one(db_session, ctx, "Q1")
    url = f"/api/hr/answers/{answer.id}/override"

    resp = hr_client.post(
        url,
        content="score=3&reason=x",
        headers={"content-type": "text/plain"},
    )
    assert resp.status_code == 415
    assert resp.json()["detail"] == "content type must be application/json"

    resp = hr_client.post(
        url,
        content="score=3&reason=x",
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    assert resp.status_code == 415


def test_override_on_superseded_and_unknown(hr_client, ctx, db_session):
    from app.core.time import utcnow

    answer = answer_one(db_session, ctx, "Q1")
    answer.superseded_at = utcnow()
    db_session.commit()

    resp = hr_client.post(f"/api/hr/answers/{answer.id}/override", json={"score": 3, "reason": "x"})
    assert resp.status_code == 409
    assert resp.json()["detail"] == "answer has been replaced by a newer submission"

    resp = hr_client.post("/api/hr/answers/missing/override", json={"score": 3, "reason": "x"})
    assert resp.status_code == 404
    assert resp.json()["detail"] == "answer not found"


def test_accept_happy_and_repeat(hr_client, ctx, db_session):
    answer = answer_one(db_session, ctx, "Q1")
    set_job_result(db_session, answer, status=JobStatus.SCORED, score=3, reason="good")

    resp = hr_client.post(f"/api/hr/answers/{answer.id}/accept", json={"score": 3})
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["kind"] == "accept"
    assert data["reason"] is None

    again = hr_client.post(f"/api/hr/answers/{answer.id}/accept", json={"score": 3})
    assert again.status_code == 200
    assert again.json()["id"] == data["id"]


def test_accept_mismatch_and_missing_suggestion(hr_client, ctx, db_session):
    scored = answer_one(db_session, ctx, "Q1")
    set_job_result(db_session, scored, status=JobStatus.SCORED, score=3, reason="good")
    resp = hr_client.post(f"/api/hr/answers/{scored.id}/accept", json={"score": 2})
    assert resp.status_code == 409
    assert resp.json()["detail"] == "suggested score has changed, reload and try again"

    failed = answer_one(db_session, ctx, "Q2")
    set_job_result(db_session, failed, status=JobStatus.FAILED)
    resp = hr_client.post(f"/api/hr/answers/{failed.id}/accept", json={"score": 3})
    assert resp.status_code == 409
    assert resp.json()["detail"] == "no suggested score to accept"

    queued = answer_one(db_session, ctx, "Q3")
    resp = hr_client.post(f"/api/hr/answers/{queued.id}/accept", json={"score": 3})
    assert resp.status_code == 409
    assert resp.json()["detail"] == "no suggested score to accept"


def test_accept_on_needs_person_rejected(hr_client, ctx, db_session):
    answer = answer_one(db_session, ctx, "Q1")
    set_job_result(
        db_session,
        answer,
        status=JobStatus.NEEDS_PERSON,
        score=2,
        reason="maybe",
        needs_person_reason="unclear",
    )
    resp = hr_client.post(f"/api/hr/answers/{answer.id}/accept", json={"score": 2})
    assert resp.status_code == 409
    assert resp.json()["detail"] == "needs a person: use override with a reason"


def test_retry_failed_job(hr_client, ctx, db_session):
    answer = answer_one(db_session, ctx, "Q1")
    job = set_job_result(db_session, answer, status=JobStatus.FAILED)

    resp = hr_client.post(f"/api/hr/jobs/{job.id}/retry", json={})
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "queued"

    again = hr_client.post(f"/api/hr/jobs/{job.id}/retry", json={})
    assert again.status_code == 200


def test_retry_non_failed_and_unknown(hr_client, ctx, db_session):
    answer = answer_one(db_session, ctx, "Q1")
    job = set_job_result(db_session, answer, status=JobStatus.SCORED, score=3, reason="ok")

    resp = hr_client.post(f"/api/hr/jobs/{job.id}/retry", json={})
    assert resp.status_code == 409
    assert resp.json()["detail"] == "only failed jobs can be retried"

    resp = hr_client.post("/api/hr/jobs/99999/retry", json={})
    assert resp.status_code == 404
    assert resp.json()["detail"] == "job not found"


def test_retry_requires_json(hr_client, ctx, db_session):
    answer = answer_one(db_session, ctx, "Q1")
    job = set_job_result(db_session, answer, status=JobStatus.FAILED)

    resp = hr_client.post(f"/api/hr/jobs/{job.id}/retry")
    assert resp.status_code == 415
    assert resp.json()["detail"] == "content type must be application/json"

    resp = hr_client.post(
        f"/api/hr/jobs/{job.id}/retry",
        content="{}",
        headers={"content-type": "text/plain"},
    )
    assert resp.status_code == 415


def test_review_reflects_override(hr_client, ctx, db_session):
    answer = answer_one(db_session, ctx, "Q1")
    set_job_result(db_session, answer, status=JobStatus.SCORED, score=2, reason="ok")
    hr_client.post(
        f"/api/hr/answers/{answer.id}/override",
        json={"score": 4, "reason": "better"},
    )

    resp = hr_client.get(f"/api/hr/candidates/{ctx.id}")
    entry = next(q["answer"] for q in resp.json()["questions"] if q["question"]["id"] == "Q1")
    assert entry["final_score"] == 4
    assert entry["final_source"] == "hr"
    assert entry["decisions"][0]["score"] == 4
