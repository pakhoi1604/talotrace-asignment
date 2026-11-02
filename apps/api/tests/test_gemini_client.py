from types import SimpleNamespace

import httpx
import pytest
from google.genai import errors, types

from app.scoring.llm_client import (
    GeminiScoringLLM,
    LLMRefusal,
    PermanentLLMError,
    RateLimited,
    TransientLLMError,
)


def make_llm(result=None) -> GeminiScoringLLM:
    """Client with the SDK call replaced by a stub (no network)."""
    llm = GeminiScoringLLM(api_key="k", model="gemini-test", timeout_s=5, max_output_tokens=512)
    llm._client = _StubClient(result)
    return llm


class _StubModels:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def generate_content(self, *, model, contents, config):
        self.calls.append({"model": model, "contents": contents, "config": config})
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class _StubClient:
    def __init__(self, result):
        self.models = _StubModels(result)


def ok_response(text: str = '{"score": 3, "reason": "r", "instruction_attempt": false}'):
    return SimpleNamespace(
        prompt_feedback=None,
        candidates=[SimpleNamespace(finish_reason=types.FinishReason.STOP)],
        text=text,
    )


def client_error(code: int, details=None):
    body = {"error": {"code": code, "message": f"err {code}"}}
    if details is not None:
        body["error"]["details"] = details
    return errors.ClientError(code, body)


# --- error mapping -------------------------------------------------------------


def test_429_rate_limited_with_retry_delay():
    llm = make_llm(
        client_error(
            429,
            details=[
                {
                    "@type": "type.googleapis.com/google.rpc.RetryInfo",
                    "retryDelay": "12s",
                }
            ],
        )
    )
    with pytest.raises(RateLimited) as exc:
        llm.generate(system="s", user="u")
    assert exc.value.retry_after == 12.0


def test_429_default_retry_delay():
    llm = make_llm(client_error(429))
    with pytest.raises(RateLimited) as exc:
        llm.generate(system="s", user="u")
    assert exc.value.retry_after == 30.0


@pytest.mark.parametrize("code", [400, 401, 403, 404])
def test_client_errors_permanent(code):
    llm = make_llm(client_error(code))
    with pytest.raises(PermanentLLMError):
        llm.generate(system="s", user="u")


def test_408_transient():
    llm = make_llm(client_error(408))
    with pytest.raises(TransientLLMError):
        llm.generate(system="s", user="u")


@pytest.mark.parametrize(
    "err",
    [
        errors.ServerError(500, {"error": {"message": "boom"}}),
        errors.APIError(502, {"error": {"message": "bad gateway"}}),
        errors.UnknownApiResponseError("weird response"),
        httpx.TimeoutException("timed out"),
        httpx.TransportError("conn reset"),
    ],
)
def test_transient_errors(err):
    llm = make_llm(err)
    with pytest.raises(TransientLLMError):
        llm.generate(system="s", user="u")


# --- response handling ---------------------------------------------------------


def test_prompt_feedback_block_reason_refusal():
    resp = SimpleNamespace(
        prompt_feedback=SimpleNamespace(block_reason=types.BlockedReason.SAFETY),
        candidates=[SimpleNamespace(finish_reason=None)],
        text=None,
    )
    with pytest.raises(LLMRefusal) as exc:
        make_llm(resp).generate(system="s", user="u")
    assert "SAFETY" in str(exc.value)


@pytest.mark.parametrize(
    "reason",
    [
        types.FinishReason.SAFETY,
        types.FinishReason.RECITATION,
        types.FinishReason.LANGUAGE,
        types.FinishReason.SPII,
        types.FinishReason.BLOCKLIST,
        types.FinishReason.PROHIBITED_CONTENT,
        types.FinishReason.OTHER,
    ],
)
def test_non_stop_finish_reason_refusal(reason):
    resp = SimpleNamespace(
        prompt_feedback=None,
        candidates=[SimpleNamespace(finish_reason=reason)],
        text="partial",
    )
    with pytest.raises(LLMRefusal) as exc:
        make_llm(resp).generate(system="s", user="u")
    assert reason.name in str(exc.value)


def test_max_tokens_transient():
    resp = SimpleNamespace(
        prompt_feedback=None,
        candidates=[SimpleNamespace(finish_reason=types.FinishReason.MAX_TOKENS)],
        text="truncated",
    )
    with pytest.raises(TransientLLMError):
        make_llm(resp).generate(system="s", user="u")


def test_empty_text_stop_transient():
    resp = SimpleNamespace(
        prompt_feedback=None,
        candidates=[SimpleNamespace(finish_reason=types.FinishReason.STOP)],
        text="",
    )
    with pytest.raises(TransientLLMError):
        make_llm(resp).generate(system="s", user="u")


def test_happy_path_returns_text():
    llm = make_llm(ok_response())
    assert llm.generate(system="s", user="u").startswith('{"score"')


# --- config --------------------------------------------------------------------


def test_config_shape():
    llm = make_llm(ok_response())
    llm.generate(system="sys", user="usr")
    cfg = llm._client.models.calls[0]["config"]
    assert cfg.system_instruction == "sys"
    assert cfg.temperature is None  # default temperature (Gemini 3 guidance)
    assert cfg.max_output_tokens == 512
    assert cfg.response_mime_type == "application/json"
    assert cfg.response_schema is not None
    assert llm._client.models.calls[0]["model"] == "gemini-test"


def test_missing_key_permanent():
    with pytest.raises(PermanentLLMError):
        GeminiScoringLLM(api_key=None, model="m", timeout_s=5, max_output_tokens=512)
    with pytest.raises(PermanentLLMError):
        GeminiScoringLLM(api_key="", model="m", timeout_s=5, max_output_tokens=512)
