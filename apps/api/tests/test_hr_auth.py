import hashlib
from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import Settings, get_settings
from app.core.time import utcnow
from app.db.session import get_db
from app.main import create_app
from app.models import HrSession
from app.services.hr_auth import (
    create_session,
    credential_fingerprint,
    delete_session,
    find_session,
    verify_credentials,
)


def _settings(**overrides):
    base = {
        "_env_file": None,
        "HR_EMAIL": "hr@test.local",
        "HR_PASSWORD": "pw",
        "HR_SESSION_TTL_HOURS": 12,
        "HR_COOKIE_SECURE": False,
    }
    base.update(overrides)
    return Settings(**base)


def test_verify_credentials():
    settings = _settings()
    assert verify_credentials(settings, "hr@test.local", "pw") is True
    assert verify_credentials(settings, "hr@test.local", "nope") is False
    assert verify_credentials(settings, "other@test.local", "pw") is False


def test_verify_credentials_trims_and_casefolds_email():
    settings = _settings()
    assert verify_credentials(settings, "  HR@Test.Local ", "pw") is True


def test_verify_credentials_unconfigured():
    settings = _settings(HR_PASSWORD=None)
    assert verify_credentials(settings, "hr@test.local", "pw") is False


def test_blank_password_setting_loads_as_none():
    assert Settings(_env_file=None, HR_PASSWORD="  ").HR_PASSWORD is None
    assert Settings(_env_file=None, HR_EMAIL="").HR_EMAIL is None


def test_create_session_stores_hash_and_canonical_email(db_session):
    settings = _settings()
    raw = create_session(db_session, settings)
    row = db_session.scalar(select(HrSession))
    assert row is not None
    assert row.token_hash == hashlib.sha256(raw.encode()).hexdigest()
    assert row.token_hash != raw
    assert row.email == "hr@test.local"
    assert row.credential_fingerprint == credential_fingerprint(settings)


def test_find_session_from_a_second_session(db_session, session_factory):
    settings = _settings()
    raw = create_session(db_session, settings)

    other = session_factory()
    try:
        assert find_session(other, raw, settings) is not None
        assert find_session(other, "unknown-token", settings) is None
    finally:
        other.close()


def test_find_session_expired(db_session):
    settings = _settings()
    raw = create_session(db_session, settings)
    row = db_session.scalar(select(HrSession))
    row.expires_at = utcnow() - timedelta(hours=1)
    db_session.commit()
    assert find_session(db_session, raw, settings) is None


def test_find_session_revoked_when_account_changes(db_session):
    settings = _settings()
    raw = create_session(db_session, settings)
    assert find_session(db_session, raw, settings) is not None

    assert find_session(db_session, raw, _settings(HR_PASSWORD="new-pw")) is None
    assert find_session(db_session, raw, _settings(HR_EMAIL="boss@test.local")) is None
    assert find_session(db_session, raw, _settings(HR_PASSWORD=None)) is None


def test_delete_session(db_session):
    settings = _settings()
    raw = create_session(db_session, settings)
    delete_session(db_session, raw)
    assert find_session(db_session, raw, settings) is None
    # deleting again is a no-op
    delete_session(db_session, raw)


def _client_with_settings(session_factory, settings):
    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_settings] = lambda: settings
    return TestClient(app)


def test_sign_in_sets_httponly_cookie(client):
    resp = client.post("/api/hr/session", json={"email": "hr@test.local", "password": "pw"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["email"] == "hr@test.local"
    assert body["expires_at"].endswith(("Z", "+00:00"))
    cookie = resp.headers["set-cookie"].lower()
    for fragment in ("hr_session=", "httponly", "samesite=lax", "path=/"):
        assert fragment in cookie


def test_sign_in_normalizes_email(client):
    resp = client.post("/api/hr/session", json={"email": " HR@Test.Local ", "password": "pw"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "hr@test.local"


def test_sign_in_wrong_credentials(client):
    resp = client.post("/api/hr/session", json={"email": "hr@test.local", "password": "wrong"})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "invalid email or password"
    assert "hr_session" not in resp.headers.get("set-cookie", "")


def test_sign_in_missing_field(client):
    resp = client.post("/api/hr/session", json={"password": "pw"})
    assert resp.status_code == 422
    assert resp.json()["detail"] == "email: Field required"


def test_sign_in_non_json_body(client):
    resp = client.post(
        "/api/hr/session",
        content="email=hr@test.local&password=pw",
        headers={"content-type": "text/plain"},
    )
    assert resp.status_code == 415
    assert resp.json()["detail"] == "content type must be application/json"


def test_sign_in_unconfigured(engine, session_factory):
    client = _client_with_settings(session_factory, _settings(HR_EMAIL=None, HR_PASSWORD=None))
    resp = client.post("/api/hr/session", json={"email": "x@y.z", "password": "pw"})
    assert resp.status_code == 503
    assert resp.json()["detail"] == "hr sign-in is not configured"


def test_get_session(hr_client):
    resp = hr_client.get("/api/hr/session")
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == "hr@test.local"
    assert body["expires_at"].endswith(("Z", "+00:00"))


def test_get_session_without_cookie(client):
    resp = client.get("/api/hr/session")
    assert resp.status_code == 401
    assert resp.json()["detail"] == "invalid or missing hr session"


def test_sign_out_revokes_cookie(hr_client):
    raw = hr_client.cookies.get("hr_session")
    resp = hr_client.delete("/api/hr/session")
    assert resp.status_code == 204
    assert resp.content == b""

    # The deleted session must not authenticate anywhere else either.
    stale = TestClient(hr_client.app)
    stale.cookies.set("hr_session", raw)
    assert stale.get("/api/hr/session").status_code == 401

    assert hr_client.get("/api/hr/session").status_code == 401


def test_sign_out_without_cookie_is_noop(client):
    resp = client.delete("/api/hr/session")
    assert resp.status_code == 204
    assert resp.content == b""
