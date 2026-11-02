"""`python -m app.worker` — the scoring worker process."""

import logging
import os
import signal
import sys
import threading
import time

from sqlalchemy.orm import sessionmaker

from app.core.config import Settings, get_settings
from app.core.time import utcnow
from app.scoring.llm_client import GeminiScoringLLM, PermanentLLMError, ScoringLLM
from app.worker.runner import WorkerDeps, run_forever


class _ScrubFormatter(logging.Formatter):
    """Replace the API key value with *** in every rendered record —
    messages, args and exception tracebacks included."""

    def __init__(self, secret: str):
        super().__init__()
        self._secret = secret

    def format(self, record) -> str:
        return super().format(record).replace(self._secret, "***")


def _setup_logging(secret: str | None) -> None:
    handler = logging.StreamHandler()
    if secret:
        handler.setFormatter(_ScrubFormatter(secret))
    logging.basicConfig(level=logging.INFO, handlers=[handler])


def main(
    *,
    settings: Settings | None = None,
    session_factory: sessionmaker | None = None,
    llm: ScoringLLM | None = None,
) -> int:
    settings = settings or get_settings()
    _setup_logging(settings.GEMINI_API_KEY)
    if llm is None:
        try:
            llm = GeminiScoringLLM(
                api_key=settings.GEMINI_API_KEY,
                model=settings.GEMINI_MODEL,
                timeout_s=settings.SCORER_TIMEOUT_SECONDS,
                max_output_tokens=settings.SCORER_MAX_OUTPUT_TOKENS,
            )
        except PermanentLLMError:
            print(
                "worker: GEMINI_API_KEY is not set. Jobs stay queued. "
                "Set it in apps/api/.env and restart",
                file=sys.stderr,
            )
            return 2

    if session_factory is None:
        from app.db.session import SessionLocal

        session_factory = SessionLocal

    deps = WorkerDeps(
        session_factory=session_factory,
        llm=llm,
        settings=settings,
        sleep=time.sleep,
        now=utcnow,
        monotonic=time.monotonic,
    )

    # First signal: finish the in-flight LLM call, write, exit. Second:
    # exit now — the 120s lease recovers the job.
    stop = threading.Event()

    def _handler(_signum, _frame):
        if stop.is_set():
            os._exit(130)
        stop.set()

    signal.signal(signal.SIGINT, _handler)
    signal.signal(signal.SIGTERM, _handler)

    logging.getLogger(__name__).info("worker started, model=%s", llm.model_name)
    run_forever(deps, stop)
    return 0


if __name__ == "__main__":
    sys.exit(main())
