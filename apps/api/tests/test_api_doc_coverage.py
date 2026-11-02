import re
from pathlib import Path

from app.main import create_app

from .route_table import api_routes

DOC_PATH = Path(__file__).resolve().parents[3] / "docs" / "api-doc.md"

EXPECTED_STATUS = {
    ("GET", "/api/candidate/interview"): {200, 401},
    ("PUT", "/api/candidate/answers/{question_id}"): {201, 200, 401, 404, 409, 422},
    ("PUT", "/api/candidate/answers/{question_id}/audio"): {
        201,
        200,
        401,
        404,
        409,
        413,
        415,
        422,
    },
}

EXPECTED_DETAILS = {
    ("GET", "/api/candidate/interview"): [
        "invalid or missing candidate token",
    ],
    ("PUT", "/api/candidate/answers/{question_id}"): [
        "invalid or missing candidate token",
        "question not found",
        "answer the current question first",
        "interview is closed",
        "another submission for this question is in progress, please retry",
        "text: must not be blank",
        "text: must be at most 10000 characters",
        "body: Field required",
        "text: Field required",
    ],
    ("PUT", "/api/candidate/answers/{question_id}/audio"): [
        "invalid or missing candidate token",
        "question not found",
        "answer the current question first",
        "interview is closed",
        "another submission for this question is in progress, please retry",
        "audio file too large (max 25 MB)",
        "unsupported audio type",
        "audio file is empty",
        "file: Field required",
    ],
}

HR_EXPECTED_STATUS = {
    ("POST", "/api/hr/session"): {200, 401, 415, 422, 503},
    ("GET", "/api/hr/session"): {200, 401},
    ("DELETE", "/api/hr/session"): {204},
    ("GET", "/api/hr/roles"): {200, 401},
    ("GET", "/api/hr/roles/{role_id}/candidates"): {200, 401, 404},
    ("GET", "/api/hr/candidates/{candidate_id}"): {200, 401, 404},
    ("GET", "/api/hr/jobs"): {200, 401, 422},
    ("GET", "/api/hr/answers/{answer_id}/audio"): {200, 206, 401, 404, 416},
    ("POST", "/api/hr/answers/{answer_id}/override"): {
        201,
        200,
        401,
        404,
        409,
        415,
        422,
    },
    ("POST", "/api/hr/answers/{answer_id}/accept"): {
        201,
        200,
        401,
        404,
        409,
        415,
        422,
    },
    ("POST", "/api/hr/jobs/{job_id}/retry"): {200, 401, 404, 409, 415},
}

HR_EXPECTED_DETAILS = {
    ("POST", "/api/hr/session"): [
        "invalid email or password",
        "hr sign-in is not configured",
        "content type must be application/json",
        "email: Field required",
        "password: Field required",
    ],
    ("GET", "/api/hr/session"): [
        "invalid or missing hr session",
    ],
    ("DELETE", "/api/hr/session"): [],
    ("GET", "/api/hr/roles"): [
        "invalid or missing hr session",
    ],
    ("GET", "/api/hr/roles/{role_id}/candidates"): [
        "invalid or missing hr session",
        "role not found",
    ],
    ("GET", "/api/hr/candidates/{candidate_id}"): [
        "invalid or missing hr session",
        "candidate not found",
    ],
    ("GET", "/api/hr/jobs"): [
        "invalid or missing hr session",
    ],
    ("GET", "/api/hr/answers/{answer_id}/audio"): [
        "invalid or missing hr session",
        "audio not found",
    ],
    ("POST", "/api/hr/answers/{answer_id}/override"): [
        "invalid or missing hr session",
        "answer not found",
        "answer has been replaced by a newer submission",
        "another decision for this answer was just saved, reload and try again",
        "content type must be application/json",
        "reason: must not be blank",
        "reason: must be at most 2000 characters",
        "score: Field required",
    ],
    ("POST", "/api/hr/answers/{answer_id}/accept"): [
        "invalid or missing hr session",
        "answer not found",
        "answer has been replaced by a newer submission",
        "no suggested score to accept",
        "needs a person: use override with a reason",
        "suggested score has changed, reload and try again",
        "another decision for this answer was just saved, reload and try again",
        "content type must be application/json",
    ],
    ("POST", "/api/hr/jobs/{job_id}/retry"): [
        "invalid or missing hr session",
        "job not found",
        "only failed jobs can be retried",
        "content type must be application/json",
    ],
}


def _sections(doc: str):
    """Split the doc into (heading, body) pairs on '### ' boundaries."""
    parts = re.split(r"(?m)^### ", doc)
    for part in parts[1:]:
        heading, _, body = part.partition("\n")
        yield heading.strip(), body


def test_every_api_route_is_documented():
    doc = DOC_PATH.read_text()
    headings = {heading for heading, _ in _sections(doc)}
    app = create_app()

    routes = [r for r in api_routes(app) if r[0].startswith("/api")]
    assert routes, "expected at least one /api route"
    for path, route in routes:
        for method in route.methods - {"HEAD", "OPTIONS"}:
            assert f"{method} {path}" in headings, f"missing doc heading for {method} {path}"


def test_candidate_sections_list_every_status_code():
    doc = DOC_PATH.read_text()
    sections = dict(_sections(doc))

    for (method, path), codes in EXPECTED_STATUS.items():
        heading = f"{method} {path}"
        assert heading in sections, f"missing section {heading}"
        body = sections[heading]
        for code in codes:
            assert str(code) in body, f"{heading}: status {code} not documented"


def test_candidate_sections_list_exact_error_details():
    doc = DOC_PATH.read_text()
    sections = dict(_sections(doc))

    for (method, path), details in EXPECTED_DETAILS.items():
        body = sections[f"{method} {path}"]
        for detail in details:
            assert f"`{detail}`" in body, f"{method} {path}: detail {detail!r} missing"


def test_candidate_sections_have_required_parts():
    doc = DOC_PATH.read_text()
    sections = dict(_sections(doc))

    for method, path in EXPECTED_STATUS:
        body = sections[f"{method} {path}"]
        for marker in ("**Auth:**", "**Request:**", "**Errors:**", "```json"):
            assert marker in body, f"{method} {path}: missing {marker}"


def _status_documented(body: str, code: int) -> bool:
    """A code counts as documented as an errors-table row or a Response heading."""
    row = rf"(?m)^\|\s*{code}\s*\|"
    heading = rf"\*\*Response {code}\*\*"
    return re.search(row, body) is not None or re.search(heading, body) is not None


def test_hr_sections_list_every_status_code():
    doc = DOC_PATH.read_text()
    sections = dict(_sections(doc))

    for (method, path), codes in HR_EXPECTED_STATUS.items():
        heading = f"{method} {path}"
        assert heading in sections, f"missing section {heading}"
        body = sections[heading]
        for code in codes:
            assert _status_documented(body, code), f"{heading}: status {code} not documented"


def test_hr_sections_list_exact_error_details():
    doc = DOC_PATH.read_text()
    sections = dict(_sections(doc))

    for (method, path), details in HR_EXPECTED_DETAILS.items():
        body = sections[f"{method} {path}"]
        for detail in details:
            assert f"`{detail}`" in body, f"{method} {path}: detail {detail!r} missing"


def test_hr_sections_have_required_parts():
    doc = DOC_PATH.read_text()
    sections = dict(_sections(doc))

    for method, path in HR_EXPECTED_STATUS:
        body = sections[f"{method} {path}"]
        for marker in ("**Auth:**", "**Request:**", "**Errors:**", "```json"):
            assert marker in body, f"{method} {path}: missing {marker}"
