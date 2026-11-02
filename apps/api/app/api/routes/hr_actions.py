from contextlib import contextmanager

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_hr, require_json_content_type
from app.db.session import get_db
from app.models import HrSession
from app.models.enums import DecisionKind
from app.schemas.hr import (
    AcceptRequest,
    DecisionView,
    JobView,
    OverrideRequest,
    RetryRequest,
)
from app.services.hr_review import visible_suggestion
from app.services.score_decisions import (
    AnswerNotFound,
    AnswerSuperseded,
    ConcurrentDecision,
    JobNotFound,
    JobNotRetryable,
    NeedsPersonReview,
    NoSuggestion,
    SuggestionChanged,
    record_decision,
    retry_job,
)

router = APIRouter(
    prefix="/hr",
    tags=["hr"],
    dependencies=[Depends(require_json_content_type), Depends(get_current_hr)],
)


@contextmanager
def _domain_errors():
    """Map domain exceptions to the fixed HTTP error contract."""
    try:
        yield
    except AnswerNotFound as exc:
        raise HTTPException(status_code=404, detail="answer not found") from exc
    except AnswerSuperseded as exc:
        raise HTTPException(
            status_code=409,
            detail="answer has been replaced by a newer submission",
        ) from exc
    except NoSuggestion as exc:
        raise HTTPException(status_code=409, detail="no suggested score to accept") from exc
    except NeedsPersonReview as exc:
        raise HTTPException(
            status_code=409, detail="needs a person: use override with a reason"
        ) from exc
    except SuggestionChanged as exc:
        raise HTTPException(
            status_code=409, detail="suggested score has changed, reload and try again"
        ) from exc
    except ConcurrentDecision as exc:
        raise HTTPException(
            status_code=409,
            detail="another decision for this answer was just saved, reload and try again",
        ) from exc
    except JobNotFound as exc:
        raise HTTPException(status_code=404, detail="job not found") from exc
    except JobNotRetryable as exc:
        raise HTTPException(status_code=409, detail="only failed jobs can be retried") from exc


def _decision_view(decision) -> DecisionView:
    return DecisionView(
        id=decision.id,
        answer_id=decision.answer_id,
        kind=decision.kind,
        score=decision.score,
        reason=decision.reason,
        hr_email=decision.hr_email,
        created_at=decision.created_at,
    )


@router.post(
    "/answers/{answer_id}/override",
    response_model=DecisionView,
    status_code=201,
)
def override_score(
    answer_id: str,
    body: OverrideRequest,
    response: Response,
    db: Session = Depends(get_db),
    session: HrSession = Depends(get_current_hr),
):
    with _domain_errors():
        result = record_decision(
            db,
            answer_id,
            kind=DecisionKind.OVERRIDE,
            score=body.score,
            reason=body.reason,
            hr_email=session.email,
        )
    if not result.created:
        response.status_code = 200
    return _decision_view(result.decision)


@router.post(
    "/answers/{answer_id}/accept",
    response_model=DecisionView,
    status_code=201,
)
def accept_score(
    answer_id: str,
    body: AcceptRequest,
    response: Response,
    db: Session = Depends(get_db),
    session: HrSession = Depends(get_current_hr),
):
    with _domain_errors():
        result = record_decision(
            db,
            answer_id,
            kind=DecisionKind.ACCEPT,
            score=body.score,
            reason=None,
            hr_email=session.email,
        )
    if not result.created:
        response.status_code = 200
    return _decision_view(result.decision)


@router.post("/jobs/{job_id}/retry", response_model=JobView)
def retry_failed_job(
    job_id: int,
    _body: RetryRequest | None = None,
    db: Session = Depends(get_db),
):
    with _domain_errors():
        result = retry_job(db, job_id)
    job = result.job
    score, reason = visible_suggestion(job)
    return JobView(
        id=job.id,
        status=job.status,
        attempts=job.attempts,
        last_error=job.last_error,
        suggested_score=score,
        suggested_reason=reason,
        needs_person_reason=job.needs_person_reason,
        model=job.model,
        updated_at=job.updated_at,
    )
