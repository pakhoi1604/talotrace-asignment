"""The worker loop: claim → score → fenced write. Never dies on one job."""

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto

from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.models.enums import AnswerKind
from app.models.scoring_job import ScoringJob
from app.scoring.inputs import AnswerInput, QuestionInput
from app.scoring.llm_client import RateLimited, ScoringLLM
from app.scoring.score_answer import RunAborted, ScoringOutcome, score_answer
from app.worker import job_queue

log = logging.getLogger(__name__)


class RunKind(Enum):
    IDLE = auto()
    PROCESSED = auto()
    RATE_LIMITED = auto()


@dataclass(frozen=True)
class RunResult:
    kind: RunKind
    retry_after: float = 0.0


@dataclass
class WorkerDeps:
    session_factory: sessionmaker | Callable[[], Session]
    llm: ScoringLLM
    settings: Settings
    sleep: Callable[[float], None]
    now: Callable[[], datetime]
    monotonic: Callable[[], float]
    # Monotonic timestamp of the last LLM call — worker-scoped so the min
    # call interval holds across jobs, not just within one run.
    last_call_at: list[float] = field(default_factory=list)


def _secrets(deps: WorkerDeps) -> list[str]:
    return [deps.settings.GEMINI_API_KEY] if deps.settings.GEMINI_API_KEY else []


def _redact(message: str, deps: WorkerDeps) -> str:
    for secret in _secrets(deps):
        message = message.replace(secret, "***")
    return message[:500]


def _throttled_wait(deps: WorkerDeps) -> Callable[[float], None]:
    """Wait `extra` seconds, and keep at least WORKER_MIN_CALL_INTERVAL_SECONDS
    between LLM calls — across jobs too, not just in-run retries."""

    def wait(extra: float) -> None:
        delay = extra
        if deps.last_call_at:
            elapsed = deps.monotonic() - deps.last_call_at[0]
            delay = max(delay, deps.settings.WORKER_MIN_CALL_INTERVAL_SECONDS - elapsed)
        if delay > 0:
            deps.sleep(delay)
        deps.last_call_at[:] = [deps.monotonic()]

    return wait


def run_once(deps: WorkerDeps) -> RunResult:
    """One pass: recover stale jobs, claim one, score it, write the outcome."""
    with deps.session_factory() as db:
        job_queue.recover_stale_jobs(
            db,
            now=deps.now(),
            lease=timedelta(seconds=deps.settings.WORKER_LEASE_SECONDS),
            max_claims=deps.settings.WORKER_MAX_CLAIMS,
        )
        claim = job_queue.claim_next_job(db, now=deps.now())
        if claim is None:
            return RunResult(RunKind.IDLE)
        try:
            job = db.get(ScoringJob, claim.job_id)
            answer = job.answer
            answer_in = AnswerInput(kind=AnswerKind(answer.kind), text=answer.text)
            question_in = QuestionInput(text=answer.question.text, rubric=answer.question.rubric)
            db.commit()  # end the read txn — nothing held open across LLM calls
            outcome = score_answer(
                answer_in,
                question_in,
                deps.llm,
                max_calls=deps.settings.SCORER_MAX_CALLS,
                backoff_s=deps.settings.SCORER_BACKOFF_SECONDS,
                wait_before_call=_throttled_wait(deps),
                heartbeat=lambda: job_queue.heartbeat(db, claim, now=deps.now()),
                secrets=_secrets(deps),
            )
        except RunAborted:
            log.info("job=%s claim=%s no longer ours, stopped", claim.job_id, claim.claim_no)
            return RunResult(RunKind.PROCESSED)
        except RateLimited as exc:
            job_queue.requeue_rate_limited(db, claim, now=deps.now())
            return RunResult(RunKind.RATE_LIMITED, retry_after=exc.retry_after)
        except OperationalError:
            raise  # DB trouble: leave the job running; run_forever backs off
        except Exception as exc:
            log.exception("job=%s unexpected error", claim.job_id)
            db.rollback()
            outcome = ScoringOutcome.failed(
                _redact(f"unexpected error: {type(exc).__name__}: {exc}", deps)
            )
        written = job_queue.write_outcome(db, claim, outcome, now=deps.now())
        log.info(
            "job=%s claim=%s status=%s%s",
            claim.job_id,
            claim.claim_no,
            outcome.status.value,
            "" if written else " (discarded: no longer ours)",
        )
        return RunResult(RunKind.PROCESSED)


def run_forever(deps: WorkerDeps, stop: threading.Event) -> None:
    while not stop.is_set():
        try:
            result = run_once(deps)
        except OperationalError as exc:  # e.g. database is locked past busy_timeout
            log.warning("database error, backing off: %s", _redact(str(exc), deps))
            stop.wait(5)
            continue
        except Exception:
            log.exception("run_once failed, backing off")
            stop.wait(5)
            continue
        if result.kind is RunKind.IDLE:
            stop.wait(deps.settings.WORKER_POLL_SECONDS)
        elif result.kind is RunKind.RATE_LIMITED:
            pause = min(
                result.retry_after,
                deps.settings.WORKER_MAX_RATE_LIMIT_PAUSE_SECONDS,
            )
            log.warning("rate limited, pausing %.0fs", pause)
            stop.wait(pause)
