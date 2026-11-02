import uuid
from datetime import timedelta
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.config import Settings, get_settings, resolve_api_path
from app.core.time import utcnow
from app.db.session import get_db
from app.main import create_app
from app.models import Answer, ScoringJob
from app.models.enums import AnswerKind, JobStatus

from .factories import (
    add_decision,
    answer_one,
    make_audio_answer,
    make_candidate,
    make_role,
    seed_questions,
    set_job_result,
)

JOB_COUNT_KEYS = {"queued", "running", "scored", "failed", "needs_person"}
ALL_COUNT_KEYS = JOB_COUNT_KEYS | {"superseded"}


@pytest.fixture
def world(db_session):
    role = make_role(db_session, "Alpha Role")
    seed_questions(db_session)
    candidate, _ = make_candidate(db_session, role, "C0001")
    return SimpleNamespace(role=role, candidate=candidate)


def _answers(body):
    return {q["question"]["id"]: q["answer"] for q in body["questions"]}


def _bad_path_answer(db, candidate, question_id, *, audio_path, ext_type="audio/mp4"):
    answer = Answer(
        id=str(uuid.uuid4()),
        candidate_id=candidate.id,
        question_id=question_id,
        kind="audio",
        audio_path=audio_path,
        audio_content_type=ext_type,
        audio_size_bytes=10,
        content_sha256="b" * 64,
        submitted_at=utcnow(),
    )
    db.add(answer)
    db.add(ScoringJob(answer_id=answer.id, status=JobStatus.QUEUED))
    db.commit()
    return answer


def test_roles_list(hr_client, world, db_session):
    make_role(db_session, "Beta Role")
    make_candidate(db_session, world.role, "C0002")
    answer_one(db_session, world.candidate, "Q1")

    resp = hr_client.get("/api/hr/roles")
    assert resp.status_code == 200, resp.text
    roles = resp.json()["roles"]
    assert [r["title"] for r in roles] == sorted(r["title"] for r in roles)
    by_title = {r["title"]: r for r in roles}
    alpha = by_title["Alpha Role"]
    assert alpha["candidate_count"] == 2
    assert set(alpha["job_counts"]) == JOB_COUNT_KEYS
    assert alpha["job_counts"]["queued"] == 1
    assert by_title["Beta Role"]["candidate_count"] == 0


def test_role_candidates(hr_client, world, db_session):
    make_candidate(db_session, world.role, "C0002")
    answer_one(db_session, world.candidate, "Q1")

    resp = hr_client.get(f"/api/hr/roles/{world.role.id}/candidates")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["role"] == {"id": world.role.id, "title": "Alpha Role"}
    assert body["total_questions"] == 6
    names = [c["name"] for c in body["candidates"]]
    assert names == sorted(names)
    row = next(c for c in body["candidates"] if c["id"] == "C0001")
    assert row["answered_count"] == 1
    assert row["total_questions"] == 6
    assert set(row["job_counts"]) == JOB_COUNT_KEYS
    assert row["last_activity_at"].endswith(("Z", "+00:00"))
    empty = next(c for c in body["candidates"] if c["id"] == "C0002")
    assert empty["answered_count"] == 0
    assert empty["last_activity_at"] is None

    resp = hr_client.get("/api/hr/roles/9999/candidates")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "role not found"


def test_role_candidates_averages(hr_client, world, db_session):
    answers = [answer_one(db_session, world.candidate, f"Q{i}") for i in range(1, 5)]
    set_job_result(db_session, answers[0], status=JobStatus.SCORED, score=3, reason="good")
    set_job_result(db_session, answers[1], status=JobStatus.SCORED, score=2, reason="ok")
    set_job_result(db_session, answers[2], status=JobStatus.FAILED)
    set_job_result(
        db_session,
        answers[3],
        status=JobStatus.NEEDS_PERSON,
        score=2,
        reason="maybe",
        needs_person_reason="unclear",
    )
    add_decision(db_session, answers[1], kind="override", score=4, reason="better")

    resp = hr_client.get(f"/api/hr/roles/{world.role.id}/candidates")
    row = resp.json()["candidates"][0]
    # only `scored` suggestions count: (3 + 2) / 2, the needs_person 2 is out
    assert row["avg_suggested"] == 2.5
    # final scores: 3 (suggested) + 4 (hr override); failed/needs_person have none
    assert row["avg_final"] == 3.5


def test_role_candidates_averages_null_when_nothing_scored(hr_client, world, db_session):
    answer_one(db_session, world.candidate, "Q1")
    resp = hr_client.get(f"/api/hr/roles/{world.role.id}/candidates")
    row = resp.json()["candidates"][0]
    assert row["avg_suggested"] is None
    assert row["avg_final"] is None


def test_candidate_review_shape(hr_client, world):
    resp = hr_client.get(f"/api/hr/candidates/{world.candidate.id}")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["id"] == "C0001"
    assert body["name"] == "Candidate C0001"
    assert body["email"] == "c0001@example.com"
    assert body["role"] == {"id": world.role.id, "title": "Alpha Role"}
    assert body["total_questions"] == 6
    assert body["answered_count"] == 0
    assert [q["question"]["position"] for q in body["questions"]] == [1, 2, 3, 4, 5, 6]
    first = body["questions"][0]["question"]
    assert first["rubric"] == {"1": "level 1", "2": "level 2", "3": "level 3", "4": "level 4"}
    assert all(q["answer"] is None for q in body["questions"])


def test_text_answer_fields_and_utc_timestamps(hr_client, world, db_session):
    answer = answer_one(db_session, world.candidate, "Q1")
    resp = hr_client.get(f"/api/hr/candidates/{world.candidate.id}")
    entry = _answers(resp.json())["Q1"]
    assert entry["id"] == answer.id
    assert entry["kind"] == "text"
    assert entry["text"] == "answer Q1"
    assert entry["audio"] is None
    assert entry["submission_count"] == 1
    assert entry["decisions"] == []
    assert entry["earlier_submissions"] == []
    assert entry["final_source"] in (None, "hr", "suggested")
    job = entry["job"]
    assert job["status"] == "queued"
    for key in ("submitted_at",):
        assert entry[key].endswith(("Z", "+00:00"))
    assert job["updated_at"].endswith(("Z", "+00:00"))


def test_resubmission_shows_earlier_submissions(hr_client, world, db_session):
    from app.services.answer_submission import record_answer, text_sha256

    old = answer_one(db_session, world.candidate, "Q1", text="v1")
    result = record_answer(
        db_session,
        world.candidate,
        "Q1",
        kind=AnswerKind.TEXT,
        content_sha256=text_sha256("v2"),
        text="v2",
    )
    new = result.answer

    resp = hr_client.get(f"/api/hr/candidates/{world.candidate.id}")
    body = resp.json()
    entry = _answers(body)["Q1"]
    assert entry["id"] == new.id
    assert entry["text"] == "v2"
    assert entry["submission_count"] == 2
    earlier = entry["earlier_submissions"]
    assert len(earlier) == 1
    assert earlier[0]["id"] == old.id
    assert earlier[0]["superseded_at"].endswith(("Z", "+00:00"))
    # the superseded job does not count
    assert set(body["job_counts"]) == JOB_COUNT_KEYS
    assert body["job_counts"]["queued"] == 1


def test_decisions_survive_resubmission(hr_client, world, db_session):
    from app.services.answer_submission import record_answer, text_sha256

    old = answer_one(db_session, world.candidate, "Q1", text="v1")
    add_decision(db_session, old, kind="override", score=4, reason="strong yes")
    record_answer(
        db_session,
        world.candidate,
        "Q1",
        kind=AnswerKind.TEXT,
        content_sha256=text_sha256("v2"),
        text="v2",
    )

    entry = _answers(hr_client.get(f"/api/hr/candidates/{world.candidate.id}").json())["Q1"]
    assert entry["decisions"] == []
    assert entry["final_source"] in (None, "suggested")
    kept = entry["earlier_submissions"][0]["decisions"]
    assert len(kept) == 1
    assert kept[0]["kind"] == "override"
    assert kept[0]["score"] == 4
    assert kept[0]["reason"] == "strong yes"


def test_failed_job_hides_score(hr_client, world, db_session):
    answer = answer_one(db_session, world.candidate, "Q1")
    set_job_result(db_session, answer, status=JobStatus.FAILED)

    entry = _answers(hr_client.get(f"/api/hr/candidates/{world.candidate.id}").json())["Q1"]
    assert entry["job"]["status"] == "failed"
    assert entry["job"]["suggested_score"] is None
    assert entry["job"]["suggested_reason"] is None
    assert entry["job"]["last_error"]
    assert entry["final_score"] is None
    assert entry["final_source"] is None


def test_failed_job_with_score_in_db_still_hidden(hr_client, world, db_session):
    answer = answer_one(db_session, world.candidate, "Q1")
    db_session.execute(
        text(
            "UPDATE scoring_jobs SET status='failed', suggested_score=2,"
            " suggested_reason='raw sql', attempts=1 WHERE answer_id=:aid"
        ),
        {"aid": answer.id},
    )
    db_session.commit()

    resp = hr_client.get(f"/api/hr/candidates/{world.candidate.id}")
    entry = _answers(resp.json())["Q1"]
    assert entry["job"]["status"] == "failed"
    assert entry["job"]["suggested_score"] is None
    assert entry["final_score"] is None

    role_resp = hr_client.get(f"/api/hr/roles/{world.role.id}/candidates")
    assert role_resp.json()["candidates"][0]["avg_suggested"] is None


def test_needs_person_shows_suggestion_without_final(hr_client, world, db_session):
    answer = answer_one(db_session, world.candidate, "Q1")
    set_job_result(
        db_session,
        answer,
        status=JobStatus.NEEDS_PERSON,
        score=2,
        reason="borderline",
        needs_person_reason="unclear audio",
    )
    entry = _answers(hr_client.get(f"/api/hr/candidates/{world.candidate.id}").json())["Q1"]
    assert entry["job"]["suggested_score"] == 2
    assert entry["job"]["needs_person_reason"] == "unclear audio"
    assert entry["final_score"] is None
    assert entry["final_source"] is None


def test_decisions_newest_first_and_final_source(hr_client, world, db_session):
    answer = answer_one(db_session, world.candidate, "Q1")
    set_job_result(db_session, answer, status=JobStatus.SCORED, score=2, reason="ok")
    add_decision(db_session, answer, kind="override", score=4, reason="better")
    add_decision(db_session, answer, kind="override", score=3, reason="revised")

    entry = _answers(hr_client.get(f"/api/hr/candidates/{world.candidate.id}").json())["Q1"]
    decisions = entry["decisions"]
    assert [d["score"] for d in decisions] == [3, 4]
    for d in decisions:
        assert set(d) >= {"id", "kind", "score", "reason", "hr_email", "created_at"}
        assert d["hr_email"] == "hr@test.local"
        assert d["created_at"].endswith(("Z", "+00:00"))
    assert entry["final_score"] == 3
    assert entry["final_source"] == "hr"


def test_suggested_final_source(hr_client, world, db_session):
    answer = answer_one(db_session, world.candidate, "Q1")
    set_job_result(db_session, answer, status=JobStatus.SCORED, score=3, reason="good")
    entry = _answers(hr_client.get(f"/api/hr/candidates/{world.candidate.id}").json())["Q1"]
    assert entry["final_score"] == 3
    assert entry["final_source"] == "suggested"


def test_audio_answer_fields(hr_client, world, db_session, upload_dir):
    answer = make_audio_answer(db_session, world.candidate, "Q1", upload_dir)
    entry = _answers(hr_client.get(f"/api/hr/candidates/{world.candidate.id}").json())["Q1"]
    assert entry["kind"] == "audio"
    assert entry["text"] is None
    assert entry["audio"] == {
        "content_type": "audio/mp4",
        "size_bytes": answer.audio_size_bytes,
        "url": f"/api/hr/answers/{answer.id}/audio",
    }


def test_unknown_candidate(hr_client):
    resp = hr_client.get("/api/hr/candidates/NOPE")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "candidate not found"


def test_jobs_list(hr_client, world, db_session):
    answers = [answer_one(db_session, world.candidate, f"Q{i}") for i in range(1, 4)]
    jobs = [a.job for a in answers]
    set_job_result(db_session, answers[1], status=JobStatus.FAILED)
    # deterministic order: newest updated_at first
    for i, job in enumerate(jobs):
        db_session.execute(
            text("UPDATE scoring_jobs SET updated_at=:ts WHERE id=:jid"),
            {"ts": utcnow() + timedelta(minutes=i), "jid": job.id},
        )
    db_session.commit()

    resp = hr_client.get("/api/hr/jobs")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert set(body["counts"]) == ALL_COUNT_KEYS
    assert body["counts"]["failed"] == 1
    assert body["counts"]["queued"] == 2
    ids = [j["id"] for j in body["jobs"]]
    assert ids == [jobs[2].id, jobs[1].id, jobs[0].id]
    item = body["jobs"][0]
    assert item["candidate"] == {"id": "C0001", "name": "Candidate C0001"}
    assert item["role"] == {"id": world.role.id, "title": "Alpha Role"}
    assert item["answer"]["question_id"] == "Q3"
    assert "suggested_score" not in item
    assert item["updated_at"].endswith(("Z", "+00:00"))


def test_jobs_list_excludes_superseded_by_default(hr_client, world, db_session):
    from app.services.answer_submission import record_answer, text_sha256

    answer_one(db_session, world.candidate, "Q1", text="v1")
    record_answer(
        db_session,
        world.candidate,
        "Q1",
        kind=AnswerKind.TEXT,
        content_sha256=text_sha256("v2"),
        text="v2",
    )
    resp = hr_client.get("/api/hr/jobs")
    body = resp.json()
    assert all(j["status"] != "superseded" for j in body["jobs"])
    assert body["counts"]["superseded"] == 1

    resp = hr_client.get("/api/hr/jobs", params={"status": "superseded"})
    statuses = {j["status"] for j in resp.json()["jobs"]}
    assert statuses == {"superseded"}


def test_jobs_list_status_filter(hr_client, world, db_session):
    answers = [answer_one(db_session, world.candidate, f"Q{i}") for i in range(1, 3)]
    set_job_result(db_session, answers[0], status=JobStatus.FAILED)

    resp = hr_client.get("/api/hr/jobs", params={"status": "failed"})
    assert resp.status_code == 200
    assert {j["status"] for j in resp.json()["jobs"]} == {"failed"}

    resp = hr_client.get("/api/hr/jobs", params={"status": "bogus"})
    assert resp.status_code == 422
    assert resp.json()["detail"].startswith("status:")


def test_audio_streams_bytes(hr_client, world, db_session, upload_dir):
    answer = make_audio_answer(db_session, world.candidate, "Q1", upload_dir)
    payload = (upload_dir / answer.audio_path).read_bytes()

    resp = hr_client.get(f"/api/hr/answers/{answer.id}/audio")
    assert resp.status_code == 200
    assert resp.content == payload
    assert resp.headers["content-type"].startswith("audio/mp4")
    assert resp.headers["x-content-type-options"] == "nosniff"
    assert "sandbox" in resp.headers["content-security-policy"]


def test_audio_ignores_hostile_stored_content_type(hr_client, world, db_session, upload_dir):
    answer = make_audio_answer(
        db_session, world.candidate, "Q1", upload_dir, content_type="audio/x, text/html"
    )
    resp = hr_client.get(f"/api/hr/answers/{answer.id}/audio")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("audio/mp4")


def test_audio_range_request(hr_client, world, db_session, upload_dir):
    answer = make_audio_answer(db_session, world.candidate, "Q1", upload_dir)
    payload = (upload_dir / answer.audio_path).read_bytes()

    resp = hr_client.get(f"/api/hr/answers/{answer.id}/audio", headers={"Range": "bytes=0-3"})
    assert resp.status_code == 206
    assert resp.content == payload[:4]

    resp = hr_client.get(
        f"/api/hr/answers/{answer.id}/audio",
        headers={"Range": f"bytes={len(payload) + 100}-"},
    )
    assert resp.status_code == 416


def test_audio_not_found_cases(hr_client, world, db_session, upload_dir):
    text_answer = answer_one(db_session, world.candidate, "Q1")
    resp = hr_client.get(f"/api/hr/answers/{text_answer.id}/audio")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "audio not found"

    resp = hr_client.get("/api/hr/answers/no-such-answer/audio")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "audio not found"

    missing = make_audio_answer(db_session, world.candidate, "Q2", upload_dir)
    (upload_dir / missing.audio_path).unlink()
    assert hr_client.get(f"/api/hr/answers/{missing.id}/audio").status_code == 404

    escape = _bad_path_answer(db_session, world.candidate, "Q3", audio_path="../escape.m4a")
    assert hr_client.get(f"/api/hr/answers/{escape.id}/audio").status_code == 404

    (upload_dir / "notes.txt").write_text("not audio")
    weird = _bad_path_answer(db_session, world.candidate, "Q4", audio_path="notes.txt")
    assert hr_client.get(f"/api/hr/answers/{weird.id}/audio").status_code == 404


def test_audio_relative_upload_dir(db_session, session_factory, world):
    settings = Settings(
        _env_file=None,
        UPLOAD_DIR="uploads",
        HR_EMAIL="hr@test.local",
        HR_PASSWORD="pw",
        HR_COOKIE_SECURE=False,
        HR_SESSION_TTL_HOURS=12,
    )

    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_settings] = lambda: settings
    client = TestClient(app)
    client.post("/api/hr/session", json={"email": "hr@test.local", "password": "pw"})

    rel_dir = resolve_api_path("uploads")
    rel_dir.mkdir(parents=True, exist_ok=True)
    filename = f"rel-{uuid.uuid4()}.m4a"
    target = rel_dir / filename
    target.write_bytes(b"rel-bytes")
    try:
        answer = _bad_path_answer(db_session, world.candidate, "Q1", audio_path=filename)
        resp = client.get(f"/api/hr/answers/{answer.id}/audio")
        assert resp.status_code == 200
        assert resp.content == b"rel-bytes"
    finally:
        target.unlink(missing_ok=True)
