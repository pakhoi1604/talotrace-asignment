import pytest

from app.models import Answer, Role, ScoringJob
from app.models.enums import JobStatus

from .factories import make_candidate, make_role, seed_questions

AUTH = "invalid or missing candidate token"
INTERVIEW = "/api/candidate/interview"
TEXT_URL = "/api/candidate/answers/{qid}"
AUDIO_URL = "/api/candidate/answers/{qid}/audio"


@pytest.fixture
def candidate_client(client, session_factory):
    db = session_factory()
    role = make_role(db)
    candidate, token = make_candidate(db, role)
    seed_questions(db)
    db.close()
    return client, candidate, token


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _put_text(client, token, qid, text):
    return client.put(TEXT_URL.format(qid=qid), json={"text": text}, headers=_auth(token))


def _put_audio(client, token, qid, name="clip.m4a", data=b"fake-audio", ctype="audio/mp4"):
    return client.put(
        AUDIO_URL.format(qid=qid),
        files={"file": (name, data, ctype)},
        headers=_auth(token),
    )


def _assert_401(response):
    assert response.status_code == 401
    assert response.json() == {"detail": AUTH}


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Authorization": "Token abc"},
        {"Authorization": "Bearer"},
        {"Authorization": "Bearer totally-unknown"},
    ],
    ids=["missing", "wrong-scheme", "empty-token", "unknown-token"],
)
def test_bad_auth_rejected_on_all_endpoints(candidate_client, headers):
    client, _, _ = candidate_client
    _assert_401(client.get(INTERVIEW, headers=headers))
    _assert_401(client.put(TEXT_URL.format(qid="Q1"), json={"text": "x"}, headers=headers))
    _assert_401(
        client.put(
            AUDIO_URL.format(qid="Q1"),
            files={"file": ("a.m4a", b"x", "audio/mp4")},
            headers=headers,
        )
    )


def test_rotated_token_rejected(candidate_client, session_factory):
    client, candidate, old_token = candidate_client
    db = session_factory()
    from app.services.candidate_access import issue_token

    issue_token(db, db.merge(candidate))
    db.commit()
    db.close()
    _assert_401(client.get(INTERVIEW, headers=_auth(old_token)))
    _assert_401(_put_text(client, old_token, "Q1", "x"))
    _assert_401(_put_audio(client, old_token, "Q1"))


def test_put_text_without_body_returns_422_string_detail(candidate_client):
    client, _, token = candidate_client
    response = client.put(TEXT_URL.format(qid="Q1"), headers=_auth(token))
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert isinstance(detail, str)
    assert detail == "body: Field required"


def test_get_fresh_interview_shows_first_question(candidate_client):
    client, candidate, token = candidate_client
    response = client.get(INTERVIEW, headers=_auth(token))
    assert response.status_code == 200
    body = response.json()
    assert body["candidate_name"] == candidate.name
    assert body["role"] == "Backend Engineer"
    assert body["total_questions"] == 6
    assert body["answered_count"] == 0
    assert body["completed"] is False
    assert body["current_question"]["id"] == "Q1"
    assert body["current_question"]["position"] == 1
    assert body["answered"] == []


def test_interview_resumes_at_current_question(candidate_client):
    client, _, token = candidate_client
    _put_text(client, token, "Q1", "answer one")

    for _ in range(2):  # reload keeps working
        body = client.get(INTERVIEW, headers=_auth(token)).json()
        assert body["current_question"]["id"] == "Q2"
        assert body["answered_count"] == 1
        assert body["answered"][0]["question_id"] == "Q1"
        assert body["answered"][0]["kind"] == "text"


def test_put_text_returns_receipt_then_replays(candidate_client, session_factory):
    client, _, token = candidate_client
    first = _put_text(client, token, "Q1", "my answer")
    assert first.status_code == 201
    receipt = first.json()
    assert receipt["question_id"] == "Q1"
    assert receipt["kind"] == "text"
    assert receipt["status"] == "received"
    assert set(receipt) == {"answer_id", "question_id", "kind", "received_at", "status"}

    replay = _put_text(client, token, "Q1", "my answer")
    assert replay.status_code == 200
    assert replay.json()["answer_id"] == receipt["answer_id"]

    db = session_factory()
    assert db.query(Answer).count() == 1
    assert db.query(ScoringJob).count() == 1
    db.close()


def test_put_different_text_supersedes(candidate_client):
    client, _, token = candidate_client
    first = _put_text(client, token, "Q1", "v1")
    second = _put_text(client, token, "Q1", "v2")

    assert second.status_code == 201
    assert second.json()["answer_id"] != first.json()["answer_id"]

    body = client.get(INTERVIEW, headers=_auth(token)).json()
    assert [a["question_id"] for a in body["answered"]] == ["Q1"]
    assert body["answered_count"] == 1


def test_out_of_order_and_unknown_question(candidate_client):
    client, _, token = candidate_client
    response = _put_text(client, token, "Q3", "skip")
    assert response.status_code == 409
    assert response.json() == {"detail": "answer the current question first"}

    response = _put_text(client, token, "Q9", "nope")
    assert response.status_code == 404
    assert response.json() == {"detail": "question not found"}


@pytest.mark.parametrize(
    ("text", "detail"),
    [
        ("   ", "text: must not be blank"),
        ("x" * 10_001, "text: must be at most 10000 characters"),
    ],
)
def test_text_validation_errors(candidate_client, text, detail):
    client, _, token = candidate_client
    response = _put_text(client, token, "Q1", text)
    assert response.status_code == 422
    assert response.json() == {"detail": detail}


def test_closed_interview_rejects_replacement(candidate_client, session_factory):
    client, candidate, token = candidate_client
    db = session_factory()
    from .factories import answer_all

    answer_all(db, db.merge(candidate))
    db.close()

    response = _put_text(client, token, "Q1", "new content")
    assert response.status_code == 409
    assert response.json() == {"detail": "interview is closed"}

    body = client.get(INTERVIEW, headers=_auth(token)).json()
    assert body["completed"] is True
    assert body["current_question"] is None


def test_audio_upload_stores_file_and_replays(candidate_client, upload_dir):
    client, _, token = candidate_client
    response = _put_audio(client, token, "Q1")
    assert response.status_code == 201
    receipt = response.json()
    assert receipt["kind"] == "audio"

    files = list(upload_dir.iterdir())
    assert len(files) == 1

    replay = _put_audio(client, token, "Q1")
    assert replay.status_code == 200
    assert replay.json()["answer_id"] == receipt["answer_id"]
    assert len(list(upload_dir.iterdir())) == 1  # replay left no extra file


def test_audio_bad_type_rejected(candidate_client, upload_dir):
    client, _, token = candidate_client
    response = _put_audio(client, token, "Q1", name="notes.txt", ctype="text/plain")
    assert response.status_code == 415
    assert response.json() == {"detail": "unsupported audio type"}
    assert list(upload_dir.iterdir()) == []


def test_audio_at_exactly_max_size_accepted(candidate_client):
    client, _, token = candidate_client
    response = _put_audio(client, token, "Q1", data=b"x" * 1024)
    assert response.status_code == 201


def test_audio_oversize_rejected(candidate_client, upload_dir):
    client, _, token = candidate_client
    response = _put_audio(client, token, "Q1", data=b"x" * 1025)
    assert response.status_code == 413
    assert response.json() == {"detail": "audio file too large (max 1 KB)"}
    assert list(upload_dir.iterdir()) == []


def test_audio_empty_file_rejected(candidate_client):
    client, _, token = candidate_client
    response = _put_audio(client, token, "Q1", data=b"")
    assert response.status_code == 422
    assert response.json() == {"detail": "audio file is empty"}


def test_audio_domain_rejection_leaves_no_file(candidate_client, upload_dir):
    client, _, token = candidate_client
    response = _put_audio(client, token, "Q9")
    assert response.status_code == 404
    response = _put_audio(client, token, "Q3")
    assert response.status_code == 409
    assert list(upload_dir.iterdir()) == []


def test_audio_missing_file_field(candidate_client):
    client, _, token = candidate_client
    response = client.put(AUDIO_URL.format(qid="Q1"), headers=_auth(token))
    assert response.status_code == 422
    assert response.json()["detail"] == "file: Field required"


FORBIDDEN_KEYS = {"score", "rubric", "reason", "job", "jobs", "email", "candidate_id"}


def _walk_keys(node):
    if isinstance(node, dict):
        for key, value in node.items():
            yield key, value
            yield from _walk_keys(value)
    elif isinstance(node, list):
        for item in node:
            yield from _walk_keys(item)


def _assert_no_leaks(body):
    for key, value in _walk_keys(body):
        assert key not in FORBIDDEN_KEYS
        if key == "status":
            assert value == "received"


def test_candidate_responses_never_leak_grades_or_hr_data(candidate_client, session_factory):
    client, candidate, token = candidate_client
    db = session_factory()
    # give the answer a job in a non-queued state to tempt leaks
    _put_text(client, token, "Q1", "first")
    job = db.query(ScoringJob).one()
    job.status = JobStatus.SCORED
    db.commit()
    db.close()

    bodies = [
        client.get(INTERVIEW, headers=_auth(token)).json(),
        _put_text(client, token, "Q1", "second").json(),
        _put_audio(client, token, "Q2").json(),
        client.get(INTERVIEW, headers=_auth(token)).json(),
    ]
    for body in bodies:
        _assert_no_leaks(body)


def test_candidate_cannot_see_other_candidates_data(candidate_client, session_factory):
    client, candidate, token = candidate_client
    db = session_factory()
    role = db.get(Role, candidate.role_id)
    other, other_token = make_candidate(db, role, id="C0002")
    db.close()

    _put_text(client, token, "Q1", "mine")

    body = client.get(INTERVIEW, headers=_auth(other_token)).json()
    assert body["candidate_name"] == other.name
    assert body["answered_count"] == 0
    assert body["answered"] == []
