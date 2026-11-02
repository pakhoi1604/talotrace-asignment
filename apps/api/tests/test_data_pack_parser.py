import json

import pytest

from app.seed.data_pack_parser import (
    DataPackError,
    load_pack_answers,
    load_pipeline_people,
    parse_questions_md,
)

from .conftest import PACK_DIR


def test_parse_real_questions_md():
    parsed = parse_questions_md(PACK_DIR / "questions.md")

    assert len(parsed.roles) == 5
    assert "Backend Engineer" in parsed.roles
    assert [q.id for q in parsed.questions] == ["Q1", "Q2", "Q3", "Q4", "Q5", "Q6"]
    for question in parsed.questions:
        assert question.text
        assert set(question.rubric) == {"1", "2", "3", "4"}


def test_parse_questions_md_missing_rubric_level(tmp_path):
    bad = tmp_path / "questions.md"
    bad.write_text(
        "# Interview questions\n\n"
        "Open roles: Backend Engineer.\n\n"
        "## Q1. A question?\n\n"
        "- **1:** Bad.\n- **2:** Meh.\n- **3:** Good.\n"
    )
    with pytest.raises(DataPackError):
        parse_questions_md(bad)


def test_load_pack_answers_real_pack():
    people = load_pipeline_people(PACK_DIR / "pipeline_log.csv")
    answers = load_pack_answers(PACK_DIR / "answers", people)

    assert len(answers) == 35
    audio = [a for a in answers if a.transcript is None]
    assert sorted(a.answer_id for a in audio) == ["A031", "A032", "A033", "A034", "A035"]
    for answer in audio:
        assert answer.audio_path is not None
        assert answer.audio_path.exists()
    text = [a for a in answers if a.transcript is not None]
    assert len(text) == 30


def test_load_pack_answers_unknown_candidate_rejected(tmp_path):
    answers_dir = tmp_path / "answers"
    answers_dir.mkdir()
    (answers_dir / "A001.json").write_text(
        json.dumps(
            {
                "answer_id": "A001",
                "candidate_id": "C9999",
                "role": "Backend Engineer",
                "question_id": "Q1",
                "submitted_at": "2026-09-14T10:15:00",
                "transcript": "hi",
            }
        )
    )
    people = load_pipeline_people(PACK_DIR / "pipeline_log.csv")

    with pytest.raises(DataPackError):
        load_pack_answers(answers_dir, people)


def test_load_pipeline_people_has_pack_candidates():
    people = load_pipeline_people(PACK_DIR / "pipeline_log.csv")

    assert "C2041" in people
    person = people["C2041"]
    assert person.name and person.email and person.role
