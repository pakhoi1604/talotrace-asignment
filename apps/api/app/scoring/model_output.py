"""Strict validation of the model's JSON output before anything is stored."""

import re
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError


class ModelScore(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    score: Annotated[int, Field(ge=1, le=4)]
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
    instruction_attempt: bool


class InvalidModelOutput(Exception):
    pass


_FENCE_RE = re.compile(r"^```(?:json)?\s*(?P<body>.*?)\s*```$", re.DOTALL)


def parse_model_output(raw: str) -> ModelScore:
    text = raw.strip()
    if match := _FENCE_RE.match(text):
        text = match.group("body").strip()
    try:
        return ModelScore.model_validate_json(text)
    except (ValidationError, ValueError) as exc:
        message = str(exc).splitlines()[0][:200] if str(exc) else type(exc).__name__
        raise InvalidModelOutput(message) from exc
