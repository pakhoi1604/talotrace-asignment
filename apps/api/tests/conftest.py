from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401 — populate Base.metadata before create_all
from app.core.config import Settings, get_settings
from app.db.base import Base
from app.db.session import get_db
from app.main import create_app

PACK_DIR = Path(__file__).resolve().parents[3] / "business-systems-pack"


# Same pragmas as the production engine (app/db/session.py); foreign_keys
# matters for tests that rely on real FK violations.
@event.listens_for(Engine, "connect")
def _set_sqlite_pragmas(dbapi_connection, _connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()


@pytest.fixture
def engine(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path}/test.db", connect_args={"check_same_thread": False})
    Base.metadata.create_all(eng)
    return eng


@pytest.fixture
def session_factory(engine):
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@pytest.fixture
def db_session(session_factory):
    db = session_factory()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def upload_dir(tmp_path):
    path = tmp_path / "uploads"
    path.mkdir()
    return path


@pytest.fixture
def test_settings(upload_dir):
    # _env_file=None: a developer's apps/api/.env must not change test results.
    return Settings(
        _env_file=None,
        UPLOAD_DIR=str(upload_dir),
        MAX_AUDIO_BYTES=1024,
        HR_EMAIL="hr@test.local",
        HR_PASSWORD="pw",
        HR_COOKIE_SECURE=False,
        HR_SESSION_TTL_HOURS=12,
    )


@pytest.fixture
def client(engine, session_factory, test_settings):
    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_settings] = lambda: test_settings
    return TestClient(app)


@pytest.fixture
def hr_client(client):
    resp = client.post("/api/hr/session", json={"email": "hr@test.local", "password": "pw"})
    assert resp.status_code == 200, resp.text
    return client
