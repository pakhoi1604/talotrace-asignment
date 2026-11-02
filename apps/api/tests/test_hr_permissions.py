import re

import pytest

from app.api.deps import get_current_hr

from .factories import answer_all, make_candidate, make_role, seed_questions
from .route_table import api_routes

UNGUARDED = {("POST", "/api/hr/session"), ("DELETE", "/api/hr/session")}

# Exactly the 9 guarded routes from plan.md's endpoint table — a missing or
# extra HR route fails loudly instead of silently dropping coverage.
EXPECTED_GUARDED = {
    ("GET", "/api/hr/session"),
    ("GET", "/api/hr/roles"),
    ("GET", "/api/hr/roles/{role_id}/candidates"),
    ("GET", "/api/hr/candidates/{candidate_id}"),
    ("GET", "/api/hr/jobs"),
    ("GET", "/api/hr/answers/{answer_id}/audio"),
    ("POST", "/api/hr/answers/{answer_id}/override"),
    ("POST", "/api/hr/answers/{answer_id}/accept"),
    ("POST", "/api/hr/jobs/{job_id}/retry"),
}

DETAIL = "invalid or missing hr session"


def _dependant_uses(dependant, call) -> bool:
    if dependant.call is call:
        return True
    return any(_dependant_uses(dep, call) for dep in dependant.dependencies)


@pytest.fixture
def seeded_ids(db_session):
    role = make_role(db_session)
    seed_questions(db_session)
    candidate, token = make_candidate(db_session, role)
    answer = answer_all(db_session, candidate)[0]
    return {
        "role_id": str(role.id),
        "candidate_id": candidate.id,
        "answer_id": answer.id,
        "job_id": str(answer.job.id),
        "token": token,
    }


def _request(client, method, path, ids, headers=None):
    url = re.sub(r"{(\w+)}", lambda m: ids[m.group(1)], path)
    kwargs = {"headers": headers} if headers else {}
    if method == "GET":
        return client.get(url, **kwargs)
    if method == "DELETE":
        return client.delete(url, **kwargs)
    body = {
        "override": {"score": 4, "reason": "better"},
        "accept": {"score": 3},
    }.get(path.rsplit("/", 1)[-1], {})
    return client.post(url, json=body, **kwargs)


def _hr_routes(app):
    routes = set()
    for path, route in api_routes(app):
        if not path.startswith("/api/hr/"):
            continue
        for method in route.methods - {"HEAD", "OPTIONS"}:
            routes.add((method, path))
    return routes


def test_every_guarded_hr_route_requires_hr_session(client, seeded_ids):
    app = client.app
    routes = _hr_routes(app)
    assert routes - UNGUARDED == EXPECTED_GUARDED

    route_by_key = {}
    for path, route in api_routes(app):
        for method in route.methods - {"HEAD", "OPTIONS"}:
            route_by_key[(method, path)] = route

    for method, path in EXPECTED_GUARDED:
        route = route_by_key[(method, path)]
        assert _dependant_uses(route.dependant, get_current_hr), (
            f"{method} {path} is not guarded by get_current_hr"
        )

        resp = _request(client, method, path, seeded_ids)
        assert resp.status_code == 401, f"{method} {path}: {resp.status_code}"
        assert resp.json()["detail"] == DETAIL

        # A candidate Bearer token never opens an HR route.
        resp = _request(
            client,
            method,
            path,
            seeded_ids,
            headers={"Authorization": f"Bearer {seeded_ids['token']}"},
        )
        assert resp.status_code == 401, f"{method} {path} with bearer: {resp.status_code}"
        assert resp.json()["detail"] == DETAIL


def test_candidate_routes_reject_hr_cookie(hr_client):
    resp = hr_client.get("/api/candidate/interview")
    assert resp.status_code == 401
    assert resp.json()["detail"] == "invalid or missing candidate token"


def test_forged_cookie_rejected(client):
    client.cookies.set("hr_session", "forged-value")
    resp = client.get("/api/hr/roles")
    assert resp.status_code == 401
    assert resp.json()["detail"] == DETAIL
