import pytest
from pydantic import ValidationError

from app.scoring.model_output import InvalidModelOutput, ModelScore, parse_model_output

VALID = '{"score": 3, "reason": "solid but generic", "instruction_attempt": false}'


def test_valid_json_parses():
    ms = parse_model_output(VALID)
    assert ms.score == 3
    assert ms.reason == "solid but generic"
    assert ms.instruction_attempt is False


def test_json_fence_accepted():
    ms = parse_model_output(f"```json\n{VALID}\n```")
    assert ms.score == 3


def test_surrounding_whitespace_accepted():
    ms = parse_model_output(f"  \n{VALID}\n\t ")
    assert ms.score == 3


@pytest.mark.parametrize(
    "raw",
    [
        "not json at all",
        "[1, 2, 3]",
        '{"score": 3, "reason": "ok"}',  # missing instruction_attempt
        '{"score": 3, "reason": "ok", "instruction_attempt": false, "x": 1}',  # extra key
        '{"score": 3, "reason": "ok", "instruction_attempt": false',  # truncated
        '{"score": 0, "reason": "ok", "instruction_attempt": false}',
        '{"score": 5, "reason": "ok", "instruction_attempt": false}',
        '{"score": "3", "reason": "ok", "instruction_attempt": false}',
        '{"score": 3.5, "reason": "ok", "instruction_attempt": false}',
        '{"score": true, "reason": "ok", "instruction_attempt": false}',
        '{"score": 3, "reason": "   ", "instruction_attempt": false}',
        '{"score": 3, "reason": "", "instruction_attempt": false}',
        '{"score": 3, "reason": "ok", "instruction_attempt": "false"}',
        '{"score": 3, "reason": "ok", "instruction_attempt": 0}',
    ],
)
def test_invalid_output_rejected(raw):
    with pytest.raises(InvalidModelOutput):
        parse_model_output(raw)


def test_reason_over_2000_rejected():
    raw = '{"score": 3, "reason": "' + "x" * 2001 + '", "instruction_attempt": false}'
    with pytest.raises(InvalidModelOutput):
        parse_model_output(raw)


def test_reason_2000_accepted():
    ms = parse_model_output(
        '{"score": 3, "reason": "' + "x" * 2000 + '", "instruction_attempt": false}'
    )
    assert len(ms.reason) == 2000


def test_model_score_strict_extra_forbid():
    payload = {"score": 3, "reason": "ok", "instruction_attempt": False, "y": 0}
    with pytest.raises(ValidationError):
        ModelScore.model_validate(payload)
