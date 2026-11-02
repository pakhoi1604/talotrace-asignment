"""Gemini client + error taxonomy for the scorer.

Every failure maps to exactly one of: TransientLLMError (retry within the
run), PermanentLLMError (fail this job now), RateLimited (requeue + pause the
worker) or LLMRefusal (needs_person). Output is validated by the caller —
resp.parsed is never trusted.
"""

from typing import Protocol

import httpx
from google import genai
from google.genai import errors, types

# Schema sent to Gemini. A plain Schema — NOT the pydantic ModelScore — because
# the API 400s on the `additionalProperties` that a pydantic-derived schema
# carries. Our own parse_model_output validation is the real gate; this is a
# hint for the model's output format.
_RESPONSE_SCHEMA = types.Schema(
    type="OBJECT",
    properties={
        "score": types.Schema(type="INTEGER"),
        "reason": types.Schema(type="STRING"),
        "instruction_attempt": types.Schema(type="BOOLEAN"),
    },
    required=["score", "reason", "instruction_attempt"],
)

# httpx2 is a drop-in fork under a separate namespace; the SDK may raise
# either library's transport errors depending on which is installed.
try:
    import httpx2

    _HTTPX_ERRORS = (
        httpx.TimeoutException,
        httpx.TransportError,
        httpx2.TimeoutException,
        httpx2.TransportError,
    )
except ImportError:  # pragma: no cover
    _HTTPX_ERRORS = (httpx.TimeoutException, httpx.TransportError)


class TransientLLMError(Exception):
    """Retryable within the run: timeout, network, 5xx, bad response."""


class PermanentLLMError(Exception):
    """Fail this job at once: 400/401/403/404, missing key."""


class RateLimited(Exception):
    """429: requeue the job (claim refunded) and pause the worker."""

    def __init__(self, retry_after: float):
        super().__init__(f"rate limited, retry after {retry_after}s")
        self.retry_after = retry_after


class LLMRefusal(Exception):
    """Model declined to score (block/finish reason) → needs_person."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class ScoringLLM(Protocol):
    model_name: str

    def generate(self, *, system: str, user: str) -> str:
        """Return the raw model text (JSON). Raises the error taxonomy above."""
        ...


def _retry_delay(err: errors.APIError, default: float = 30.0) -> float:
    """Read google.rpc.RetryInfo retryDelay ("12s") from the error details."""
    details = err.details if isinstance(err.details, dict) else {}
    for item in details.get("error", {}).get("details", []) or []:
        delay = item.get("retryDelay") if isinstance(item, dict) else None
        if isinstance(delay, str) and delay.endswith("s"):
            try:
                return float(delay[:-1])
            except ValueError:
                pass
    return default


class GeminiScoringLLM:
    def __init__(
        self,
        *,
        api_key: str | None,
        model: str,
        timeout_s: float,
        max_output_tokens: int,
    ):
        if not api_key:
            raise PermanentLLMError("GEMINI_API_KEY is not set")
        self.model_name = model
        self.api_key = api_key
        self._max_tokens = max_output_tokens
        self._client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=int(timeout_s * 1000)),  # ms
        )

    def generate(self, *, system: str, user: str) -> str:
        # No temperature: Gemini 3 guidance is to leave it at the default.
        config = types.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=self._max_tokens,
            response_mime_type="application/json",
            response_schema=_RESPONSE_SCHEMA,
        )
        try:
            resp = self._client.models.generate_content(
                model=self.model_name, contents=user, config=config
            )
        except errors.ClientError as exc:
            if exc.code == 429:
                raise RateLimited(_retry_delay(exc)) from exc
            if exc.code == 408:
                raise TransientLLMError(f"request timeout: {exc.message}") from exc
            raise PermanentLLMError(f"client error {exc.code}: {exc.message}") from exc
        except (
            errors.ServerError,
            errors.UnknownApiResponseError,
            errors.APIError,
            *_HTTPX_ERRORS,
        ) as exc:
            raise TransientLLMError(f"{type(exc).__name__}: {exc}") from exc

        if resp.prompt_feedback and resp.prompt_feedback.block_reason:
            raise LLMRefusal(resp.prompt_feedback.block_reason.name)
        candidate = resp.candidates[0] if resp.candidates else None
        finish = candidate.finish_reason.name if candidate and candidate.finish_reason else None
        if finish == "MAX_TOKENS":
            raise TransientLLMError("output truncated (MAX_TOKENS)")
        if finish not in (None, "STOP"):
            raise LLMRefusal(finish)
        if not resp.text:
            raise TransientLLMError("empty response text")
        return resp.text
