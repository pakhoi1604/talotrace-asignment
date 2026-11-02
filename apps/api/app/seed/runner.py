"""Load the business-systems-pack into the database and issue access links."""

import csv
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Answer, Candidate, Question, Role, ScoringJob
from app.models.enums import AnswerKind, JobStatus
from app.seed.data_pack_parser import (
    DataPackError,
    PackPerson,
    load_pack_answers,
    load_pipeline_people,
    parse_questions_md,
)
from app.services.answer_submission import (
    AudioMeta,
    audio_sha256,
    record_answer,
    text_sha256,
)
from app.services.candidate_access import issue_token


@dataclass
class SeedLink:
    candidate_id: str
    name: str
    role: str
    link: str


@dataclass
class SeedSummary:
    roles: int
    questions: int
    candidates: int
    answers: int
    answers_current: int
    jobs: int
    jobs_queued: int
    links: list[SeedLink]


def _upsert_roles(db: Session, titles: list[str]) -> dict[str, Role]:
    existing = {r.title: r for r in db.scalars(select(Role)).all()}
    for title in titles:
        if title not in existing:
            role = Role(title=title)
            db.add(role)
            existing[title] = role
    db.flush()
    return existing


def _upsert_questions(db: Session, questions) -> None:
    for parsed in questions:
        question = db.get(Question, parsed.id)
        if question is None:
            db.add(
                Question(
                    id=parsed.id,
                    position=parsed.position,
                    text=parsed.text,
                    rubric=parsed.rubric,
                )
            )
        else:
            question.position = parsed.position
            question.text = parsed.text
            question.rubric = parsed.rubric


def _upsert_candidates(
    db: Session,
    answers,
    people: dict[str, PackPerson],
    roles_by_title: dict[str, Role],
) -> dict[str, Candidate]:
    candidates: dict[str, Candidate] = {}
    for pack_answer in answers:
        person = people[pack_answer.candidate_id]
        if pack_answer.candidate_id in candidates:
            continue
        candidate = db.get(Candidate, person.candidate_id)
        if candidate is None:
            candidate = Candidate(id=person.candidate_id, name="", email="", role_id=0)
            db.add(candidate)
        candidate.name = person.name
        candidate.email = person.email
        if person.role not in roles_by_title:
            raise DataPackError(
                f"{person.candidate_id}: pipeline role {person.role!r} not in questions.md roles"
            )
        candidate.role_id = roles_by_title[person.role].id
        candidates[person.candidate_id] = candidate
    db.flush()
    return candidates


def _import_answer(db: Session, candidate: Candidate, pack_answer, upload_dir: Path):
    if pack_answer.transcript is not None:
        return record_answer(
            db,
            candidate,
            pack_answer.question_id,
            kind=AnswerKind.TEXT,
            content_sha256=text_sha256(pack_answer.transcript),
            text=pack_answer.transcript,
            answer_id=pack_answer.answer_id,
            submitted_at=pack_answer.submitted_at,
            enforce_rules=False,
        )
    data = pack_answer.audio_path.read_bytes()
    filename = f"{pack_answer.answer_id}.m4a"
    dest = upload_dir / filename
    dest.write_bytes(data)
    try:
        result = record_answer(
            db,
            candidate,
            pack_answer.question_id,
            kind=AnswerKind.AUDIO,
            content_sha256=audio_sha256(data),
            audio=AudioMeta(path=filename, content_type="audio/mp4", size=len(data)),
            answer_id=pack_answer.answer_id,
            submitted_at=pack_answer.submitted_at,
            enforce_rules=False,
        )
    except Exception:
        dest.unlink(missing_ok=True)
        raise
    if not result.created:
        # Shouldn't happen (ids are skipped upfront) — never orphan a file.
        dest.unlink(missing_ok=True)
    return result


def run_seed(
    session_factory,
    *,
    pack_dir: Path,
    upload_dir: Path,
    links_path: Path,
    web_base_url: str,
) -> SeedSummary:
    """Load the pack, rotate every token, write the links CSV.

    Idempotent: existing rows are upserted, existing answers skipped;
    tokens are always re-issued (old links die). Returns DB counts, not
    just- inserted counts, so reruns report the same summary.
    """
    pack_dir = Path(pack_dir)
    upload_dir = Path(upload_dir)
    links_path = Path(links_path)

    parsed = parse_questions_md(pack_dir / "questions.md")
    people = load_pipeline_people(pack_dir / "pipeline_log.csv")
    pack_answers = load_pack_answers(pack_dir / "answers", people)

    role_titles = set(parsed.roles)
    question_ids = {q.id for q in parsed.questions}
    for pack_answer in pack_answers:
        if pack_answer.role not in role_titles:
            raise DataPackError(f"{pack_answer.answer_id}: unknown role {pack_answer.role!r}")
        if pack_answer.question_id not in question_ids:
            raise DataPackError(
                f"{pack_answer.answer_id}: unknown question {pack_answer.question_id!r}"
            )

    upload_dir.mkdir(parents=True, exist_ok=True)
    db = session_factory()
    try:
        roles_by_title = _upsert_roles(db, parsed.roles)
        _upsert_questions(db, parsed.questions)
        candidates = _upsert_candidates(db, pack_answers, people, roles_by_title)
        db.commit()

        for pack_answer in sorted(pack_answers, key=lambda a: (a.submitted_at, a.answer_id)):
            existing = db.get(Answer, pack_answer.answer_id)
            if existing is not None:
                # Re-copy audio if the file was wiped since the first run.
                if (
                    existing.audio_path
                    and pack_answer.audio_path is not None
                    and not (upload_dir / existing.audio_path).exists()
                ):
                    (upload_dir / existing.audio_path).write_bytes(
                        pack_answer.audio_path.read_bytes()
                    )
                continue  # already imported on an earlier run
            _import_answer(db, candidates[pack_answer.candidate_id], pack_answer, upload_dir)

        links: list[SeedLink] = []
        for candidate in db.scalars(select(Candidate).order_by(Candidate.id)).all():
            token = issue_token(db, candidate)
            links.append(
                SeedLink(
                    candidate_id=candidate.id,
                    name=candidate.name,
                    role=candidate.role.title,
                    link=f"{web_base_url}/i/{token}",
                )
            )
        db.commit()

        links_path.parent.mkdir(parents=True, exist_ok=True)
        with links_path.open("w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["candidate_id", "name", "role", "link"])
            for link in links:
                writer.writerow([link.candidate_id, link.name, link.role, link.link])

        return SeedSummary(
            roles=db.scalar(select(func.count(Role.id))) or 0,
            questions=db.scalar(select(func.count(Question.id))) or 0,
            candidates=db.scalar(select(func.count(Candidate.id))) or 0,
            answers=db.scalar(select(func.count(Answer.id))) or 0,
            answers_current=db.scalar(
                select(func.count(Answer.id)).where(Answer.superseded_at.is_(None))
            )
            or 0,
            jobs=db.scalar(select(func.count(ScoringJob.id))) or 0,
            jobs_queued=db.scalar(
                select(func.count(ScoringJob.id)).where(ScoringJob.status == JobStatus.QUEUED)
            )
            or 0,
            links=links,
        )
    finally:
        db.close()
