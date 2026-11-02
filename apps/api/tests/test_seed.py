import csv

from app.models import Answer, Candidate, Question, Role, ScoringJob
from app.models.enums import JobStatus
from app.seed.runner import run_seed
from app.services.candidate_access import find_candidate_by_token

from .conftest import PACK_DIR


def _seed(session_factory, tmp_path, web_base_url="http://localhost:3000"):
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir(exist_ok=True)
    links_path = tmp_path / "candidate-links.csv"
    summary = run_seed(
        session_factory,
        pack_dir=PACK_DIR,
        upload_dir=upload_dir,
        links_path=links_path,
        web_base_url=web_base_url,
    )
    return summary, upload_dir, links_path


def _pack_snapshot():
    files = [PACK_DIR / "questions.md", PACK_DIR / "answers" / "A001.json"]
    return {f: (f.stat().st_mtime_ns, f.stat().st_size) for f in files}


def test_seed_loads_full_pack(session_factory, tmp_path):
    summary, upload_dir, _ = _seed(session_factory, tmp_path)
    db = session_factory()

    assert db.query(Role).count() == 5
    assert db.query(Question).count() == 6
    assert db.query(Candidate).count() == 18
    assert db.query(Answer).count() == 35
    current = db.query(Answer).filter(Answer.superseded_at.is_(None)).all()
    assert len(current) == 34

    a022 = db.get(Answer, "A022")
    a023 = db.get(Answer, "A023")
    assert a022.superseded_at is not None
    assert a022.job.status == JobStatus.SUPERSEDED
    assert a023.superseded_at is None
    assert a023.job.status == JobStatus.QUEUED

    jobs = db.query(ScoringJob).all()
    assert len(jobs) == 35
    assert sum(j.status == JobStatus.QUEUED for j in jobs) == 34

    audio_files = {p.name for p in upload_dir.iterdir()}
    assert audio_files == {f"A0{n}.m4a" for n in range(31, 36)}

    assert summary.candidates == 18
    assert summary.answers == 35
    assert len(summary.links) == 18
    db.close()


def test_seed_writes_links_csv_and_tokens_resolve(session_factory, tmp_path):
    _, _, links_path = _seed(session_factory, tmp_path)
    db = session_factory()

    rows = list(csv.DictReader(links_path.open()))
    assert len(rows) == 18
    for row in rows:
        assert row["link"].startswith("http://localhost:3000/i/")
        token = row["link"].split("/i/")[1]
        found = find_candidate_by_token(db, token)
        assert found is not None
        assert found.id == row["candidate_id"]
        assert found.name == row["name"]
    db.close()


def test_seed_rerun_rotates_tokens_without_duplicates(session_factory, tmp_path):
    _, _, links_path = _seed(session_factory, tmp_path)
    first_tokens = {row["link"].split("/i/")[1] for row in csv.DictReader(links_path.open())}

    summary, _, _ = _seed(session_factory, tmp_path)
    db = session_factory()

    assert db.query(Candidate).count() == 18
    assert db.query(Answer).count() == 35
    assert db.query(ScoringJob).count() == 35

    second_tokens = {link.link.split("/i/")[1] for link in summary.links}
    assert first_tokens.isdisjoint(second_tokens)
    for token in first_tokens:
        assert find_candidate_by_token(db, token) is None
    db.close()


def test_seed_does_not_modify_pack(tmp_path, session_factory):
    before = _pack_snapshot()
    _seed(session_factory, tmp_path)
    assert _pack_snapshot() == before
