"""Turn one answer into a validated ScoringOutcome (no DB writes here)."""

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from secrets import token_hex

from app.models.enums import AnswerKind, JobStatus
from app.models.scoring_job import validate_job_result
from app.scoring.injection_scan import clean_text, detect_scorer_instructions
from app.scoring.inputs import AnswerInput, QuestionInput
from app.scoring.llm_client import (
    LLMRefusal,
    PermanentLLMError,
    RateLimited,
    ScoringLLM,
    TransientLLMError,
)
from app.scoring.model_output import InvalidModelOutput, parse_model_output
from app.scoring.prompt import build_prompt


class RunAborted(Exception):
    """Heartbeat returned False: the job was superseded or re-claimed."""


@dataclass(frozen=True)
class ScoringOutcome:
    status: JobStatus
    suggested_score: int | None = None
    suggested_reason: str | None = None
    needs_person_reason: str | None = None
    model: str | None = None
    error: str | None = None

    def __post_init__(self):
        validate_job_result(
            self.status,
            self.suggested_score,
            self.suggested_reason,
            self.needs_person_reason,
        )

    @classmethod
    def scored(cls, score: int, reason: str, model: str) -> "ScoringOutcome":
        return cls(
            status=JobStatus.SCORED,
            suggested_score=score,
            suggested_reason=reason,
            model=model,
        )

    @classmethod
    def needs_person(cls, reason: str) -> "ScoringOutcome":
        return cls(status=JobStatus.NEEDS_PERSON, needs_person_reason=reason)

    @classmethod
    def failed(cls, error: str) -> "ScoringOutcome":
        return cls(status=JobStatus.FAILED, error=error)


def _redact(message: str, secrets: Iterable[str]) -> str:
    for secret in secrets:
        if secret:
            message = message.replace(secret, "***")
    return message[:500]


def score_answer(
    answer: AnswerInput,
    question: QuestionInput,
    llm: ScoringLLM,
    *,
    max_calls: int,
    backoff_s: float,
    wait_before_call: Callable[[float], None],
    heartbeat: Callable[[], bool],
    secrets: Iterable[str] = (),
) -> ScoringOutcome:
    """Score one answer. Raises RateLimited (caller requeues) or RunAborted."""
    if answer.kind == AnswerKind.AUDIO:
        return ScoringOutcome.needs_person(
            "audio answer, not transcribed (transcription not built)"
        )
    text = answer.text or ""
    if not clean_text(text).strip():
        return ScoringOutcome.needs_person("empty answer")
    if snippet := detect_scorer_instructions(text):
        return ScoringOutcome.needs_person(
            f'answer appears to address the scorer, HR to read. Candidate text: "{snippet}"'
        )

    last_error: Exception | None = None
    for call in range(1, max_calls + 1):
        try:
            # First call goes at once; retries back off 2s, 4s. The runner
            # layers the global per-call throttle on top of this.
            wait_before_call(backoff_s * (2 ** (call - 2)) if call > 1 else 0)
            # Heartbeat after the wait so the check sits as close to the
            # paid call as possible: False = superseded/re-claimed, stop.
            if not heartbeat():
                raise RunAborted
            system, user = build_prompt(question, text, token_hex(8))
            model_score = parse_model_output(llm.generate(system=system, user=user))
            if model_score.instruction_attempt:
                return ScoringOutcome.needs_person("model flagged instructions to the scorer")
            return ScoringOutcome.scored(model_score.score, model_score.reason, llm.model_name)
        except (RunAborted, RateLimited):
            raise
        except LLMRefusal as exc:
            return ScoringOutcome.needs_person(f"model declined to score: {exc.reason}")
        except PermanentLLMError as exc:
            return ScoringOutcome.failed(_redact(str(exc), secrets))
        except (TransientLLMError, InvalidModelOutput) as exc:
            last_error = exc
        except Exception as exc:
            return ScoringOutcome.failed(
                _redact(f"unexpected error: {type(exc).__name__}: {exc}", secrets)
            )
    return ScoringOutcome.failed(_redact(f"gave up after {max_calls} calls: {last_error}", secrets))
