from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_hr, require_json_content_type
from app.core.config import Settings, get_settings, resolve_api_path
from app.db.session import get_db
from app.models import Answer
from app.models.enums import AnswerKind, JobStatus
from app.schemas.hr import (
    CandidateReview,
    JobList,
    RoleCandidates,
    RoleList,
)
from app.services.hr_review import (
    AUDIO_CONTENT_TYPES,
    get_candidate_review,
    list_jobs,
    list_role_candidates,
    list_roles,
)

# Every HR route requires a session cookie and JSON content type on writes.
router = APIRouter(
    prefix="/hr",
    tags=["hr"],
    dependencies=[Depends(require_json_content_type), Depends(get_current_hr)],
)


@router.get("/roles", response_model=RoleList)
def get_roles(db: Session = Depends(get_db)):
    return RoleList(roles=list_roles(db))


@router.get("/roles/{role_id}/candidates", response_model=RoleCandidates)
def get_role_candidates(role_id: int, db: Session = Depends(get_db)):
    result = list_role_candidates(db, role_id)
    if result is None:
        raise HTTPException(status_code=404, detail="role not found")
    return result


@router.get("/candidates/{candidate_id}", response_model=CandidateReview)
def get_review(candidate_id: str, db: Session = Depends(get_db)):
    result = get_candidate_review(db, candidate_id)
    if result is None:
        raise HTTPException(status_code=404, detail="candidate not found")
    return result


@router.get("/jobs", response_model=JobList)
def get_jobs(db: Session = Depends(get_db), status: JobStatus | None = None):
    return list_jobs(db, status)


@router.get("/answers/{answer_id}/audio")
def get_audio(
    answer_id: str,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """Stream a candidate's audio answer to HR.

    The content type comes from a fixed extension map — never from the
    stored upload header, which is candidate-controlled and could carry a
    `text/html` smuggle onto the HR origin.
    """
    answer = db.get(Answer, answer_id)
    if answer is None or answer.kind != AnswerKind.AUDIO or not answer.audio_path:
        raise HTTPException(status_code=404, detail="audio not found")

    base = resolve_api_path(settings.UPLOAD_DIR).resolve()
    path = (base / answer.audio_path).resolve()
    media_type = AUDIO_CONTENT_TYPES.get(path.suffix.lower())
    if media_type is None or not path.is_relative_to(base) or not path.is_file():
        raise HTTPException(status_code=404, detail="audio not found")

    return FileResponse(
        path,
        media_type=media_type,
        headers={
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "sandbox; default-src 'none'",
            "Content-Disposition": "inline",
        },
    )
