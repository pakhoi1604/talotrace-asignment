import re
from pathlib import Path

from fastapi.routing import APIRoute

from app.main import create_app

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


def _sections(doc: str):
    """Split the doc into (heading, body) pairs on '### ' boundaries."""
    parts = re.split(r"(?m)^### ", doc)
    for part in parts[1:]:
        heading, _, body = part.partition("\n")
        yield heading.strip(), body


def _api_routes(app):
    """Yield (path, methods) for every APIRoute, following included routers."""
    for route in app.routes:
        if isinstance(route, APIRoute):
            yield route.path, route.methods
        elif hasattr(route, "original_router"):  # Starlette >=1.10 _IncludedRouter
            prefix = route.include_context.prefix or ""
            for sub in route.original_router.routes:
                if isinstance(sub, APIRoute):
                    yield prefix + sub.path, sub.methods


def test_every_api_route_is_documented():
    doc = DOC_PATH.read_text()
    headings = {heading for heading, _ in _sections(doc)}
    app = create_app()

    api_routes = [r for r in _api_routes(app) if r[0].startswith("/api")]
    assert api_routes, "expected at least one /api route"
    for path, methods in api_routes:
        for method in methods - {"HEAD", "OPTIONS"}:
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
