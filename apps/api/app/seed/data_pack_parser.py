"""Pure parsers for business-systems-pack files. Raise DataPackError on bad data."""

import csv
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

_QUESTION_RE = re.compile(r"^## (Q\d)\. (.+)$")
_RUBRIC_RE = re.compile(r"^- \*\*(\d):\*\* (.+)$")
_ROLES_RE = re.compile(r"^Open roles: (.+)\.$")

EXPECTED_QUESTION_IDS = [f"Q{i}" for i in range(1, 7)]
RUBRIC_LEVELS = {"1", "2", "3", "4"}


class DataPackError(Exception):
    pass


@dataclass
class ParsedQuestion:
    id: str
    position: int
    text: str
    rubric: dict[str, str]


@dataclass
class ParsedQuestions:
    roles: list[str]
    questions: list[ParsedQuestion]


@dataclass
class PackPerson:
    candidate_id: str
    name: str
    email: str
    role: str


@dataclass
class PackAnswer:
    answer_id: str
    candidate_id: str
    role: str
    question_id: str
    submitted_at: datetime
    transcript: str | None
    audio_file: str | None
    audio_path: Path | None


def parse_questions_md(path: Path) -> ParsedQuestions:
    path = Path(path)
    if not path.exists():
        raise DataPackError(f"questions file not found: {path}")

    roles: list[str] = []
    questions: list[ParsedQuestion] = []
    current: ParsedQuestion | None = None

    for line in path.read_text().splitlines():
        if match := _ROLES_RE.match(line):
            roles = [r.strip() for r in match.group(1).split(",") if r.strip()]
        elif match := _QUESTION_RE.match(line):
            current = ParsedQuestion(
                id=match.group(1),
                position=len(questions) + 1,
                text=match.group(2).strip(),
                rubric={},
            )
            questions.append(current)
        elif (match := _RUBRIC_RE.match(line)) and current is not None:
            current.rubric[match.group(1)] = match.group(2).strip()

    if not roles:
        raise DataPackError(f"{path.name}: no 'Open roles:' line found")
    if [q.id for q in questions] != EXPECTED_QUESTION_IDS:
        raise DataPackError(
            f"{path.name}: expected questions {EXPECTED_QUESTION_IDS}, "
            f"got {[q.id for q in questions]}"
        )
    for question in questions:
        if set(question.rubric) != RUBRIC_LEVELS:
            raise DataPackError(
                f"{path.name}: {question.id} rubric must have levels 1-4, "
                f"got {sorted(question.rubric)}"
            )
    return ParsedQuestions(roles=roles, questions=questions)


def load_pipeline_people(path: Path) -> dict[str, PackPerson]:
    path = Path(path)
    if not path.exists():
        raise DataPackError(f"pipeline log not found: {path}")
    people: dict[str, PackPerson] = {}
    with path.open(newline="") as f:
        for row in csv.DictReader(f):
            try:
                person = PackPerson(
                    candidate_id=row["candidate_id"],
                    name=row["candidate_name"],
                    email=row["candidate_email"],
                    role=row["role"],
                )
            except KeyError as exc:
                raise DataPackError(f"{path.name}: missing column {exc}") from exc
            people[person.candidate_id] = person
    return people


def load_pack_answers(answers_dir: Path, people: dict[str, PackPerson]) -> list[PackAnswer]:
    answers_dir = Path(answers_dir)
    if not answers_dir.is_dir():
        raise DataPackError(f"answers directory not found: {answers_dir}")

    answers: list[PackAnswer] = []
    for path in sorted(answers_dir.glob("*.json")):
        try:
            raw = json.loads(path.read_text())
        except json.JSONDecodeError as exc:
            raise DataPackError(f"{path.name}: invalid JSON: {exc}") from exc

        answer_id = raw.get("answer_id") or path.stem
        candidate_id = raw.get("candidate_id", "")
        if candidate_id not in people:
            raise DataPackError(f"{path.name}: candidate_id {candidate_id!r} not in pipeline log")

        transcript = raw.get("transcript")
        audio_file = raw.get("audio_file")
        if (transcript is None) == (audio_file is None):
            raise DataPackError(f"{path.name}: exactly one of transcript/audio_file is required")

        audio_path = None
        if audio_file is not None:
            audio_path = answers_dir / audio_file
            if not audio_path.exists():
                raise DataPackError(f"{path.name}: audio file missing: {audio_file}")

        try:
            submitted_at = datetime.fromisoformat(raw["submitted_at"])
        except (KeyError, ValueError) as exc:
            raise DataPackError(f"{path.name}: missing or invalid submitted_at") from exc
        if submitted_at.tzinfo is None:
            # Pack timestamps are naive; treat as UTC (documented decision).
            submitted_at = submitted_at.replace(tzinfo=UTC)

        answers.append(
            PackAnswer(
                answer_id=answer_id,
                candidate_id=candidate_id,
                role=raw.get("role", ""),
                question_id=raw.get("question_id", ""),
                submitted_at=submitted_at,
                transcript=transcript,
                audio_file=audio_file,
                audio_path=audio_path,
            )
        )
    return answers
