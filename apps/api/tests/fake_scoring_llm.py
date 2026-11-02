"""Scripted ScoringLLM for tests: no network, records every prompt."""


class FakeScoringLLM:
    """Pops one scripted response per generate() call.

    Each response is:
    - str                  → returned as the raw model text
    - Exception            → raised
    - callable             → run as a side effect (e.g. supersede mid-run);
                             its return value is then treated like a response
    """

    def __init__(self, responses, model_name: str = "fake-gemini-1"):
        self._responses = list(responses)
        self.calls: list[dict[str, str]] = []
        self.model_name = model_name

    def generate(self, *, system: str, user: str) -> str:
        self.calls.append({"system": system, "user": user})
        if not self._responses:
            raise AssertionError("FakeScoringLLM ran out of scripted responses")
        resp = self._responses.pop(0)
        if callable(resp):
            resp = resp()
        if isinstance(resp, Exception):
            raise resp
        return resp
