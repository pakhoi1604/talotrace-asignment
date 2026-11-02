from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401 — populate Base.metadata before create_all
from app.core.config import Settings, get_settings
from app.db.base import Base
from app.db.session import get_db
from app.main import create_app

PACK_DIR = Path(__file__).resolve().parents[3] / "business-systems-pack"


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
def client(engine, session_factory, upload_dir):
    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    def override_get_settings():
        return Settings(UPLOAD_DIR=str(upload_dir), MAX_AUDIO_BYTES=1024)

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_settings] = override_get_settings
    return TestClient(app)
