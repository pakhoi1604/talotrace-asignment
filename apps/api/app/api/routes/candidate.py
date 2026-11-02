import os
import uuid
from contextlib import contextmanager

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_candidate
from app.core.config import Settings, get_settings, resolve_api_path
from app.db.session import get_db
from app.models import Answer, Candidate, Question
from app.models.enums import AnswerKind
from app.schemas.candidate import (
    AnsweredItem,
    AnswerReceipt,
    CurrentQuestion,
    InterviewView,
    TextAnswerIn,
)
from app.services.answer_submission import (
    AudioMeta,
    ConcurrentSubmission,
    InterviewClosed,
    OutOfOrder,
    QuestionNotFound,
    record_answer,
    text_sha256,
)
from app.services.audio_storage import (
    AudioTooLarge,
    EmptyUpload,
    UnsupportedAudioType,
    format_size,
    save_upload_stream,
    validate_audio_upload,
)
from app.services.interview_progress import get_progress

router = APIRouter(prefix="/candidate", tags=["candidate"])


@contextmanager
def _domain_errors():
    """Map domain exceptions to the fixed HTTP error contract."""
    try:
        yield
    except QuestionNotFound as exc:
        raise HTTPException(status_code=404, detail="question not found") from exc
    except OutOfOrder as exc:
        raise HTTPException(status_code=409, detail="answer the current question first") from exc
    except InterviewClosed as exc:
        raise HTTPException(status_code=409, detail="interview is closed") from exc
    except ConcurrentSubmission as exc:
        raise HTTPException(
            status_code=409,
            detail="another submission for this question is in progress, please retry",
        ) from exc


def _receipt(answer: Answer) -> AnswerReceipt:
    return AnswerReceipt(
        answer_id=answer.id,
        question_id=answer.question_id,
        kind=answer.kind,
        received_at=answer.submitted_at,
    )


@router.get("/interview", response_model=InterviewView)
def get_interview(
    db: Session = Depends(get_db),
    candidate: Candidate = Depends(get_current_candidate),
):
    progress = get_progress(db, candidate)
    positions = {q.id: q.position for q in db.scalars(select(Question)).all()}
    answered = sorted(progress.answered, key=lambda a: positions[a.question_id])
    return InterviewView(
        candidate_name=candidate.name,
        role=candidate.role.title,
        total_questions=progress.total,
        answered_count=len(answered),
        completed=progress.completed,
        current_question=(
            CurrentQuestion(
                id=progress.current_question.id,
                position=progress.current_question.position,
                text=progress.current_question.text,
            )
            if progress.current_question
            else None
        ),
        answered=[
            AnsweredItem(
                question_id=a.question_id,
                position=positions[a.question_id],
                kind=a.kind,
                received_at=a.submitted_at,
            )
            for a in answered
        ],
    )


@router.put("/answers/{question_id}", response_model=AnswerReceipt, status_code=201)
def submit_text_answer(
    question_id: str,
    body: TextAnswerIn,
    response: Response,
    db: Session = Depends(get_db),
    candidate: Candidate = Depends(get_current_candidate),
):
    text = body.text.strip()
    with _domain_errors():
        result = record_answer(
            db,
            candidate,
            question_id,
            kind=AnswerKind.TEXT,
            content_sha256=text_sha256(text),
            text=text,
        )
    if not result.created:
        response.status_code = 200
    return _receipt(result.answer)


@router.put("/answers/{question_id}/audio", response_model=AnswerReceipt, status_code=201)
async def submit_audio_answer(
    question_id: str,
    response: Response,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    candidate: Candidate = Depends(get_current_candidate),
    settings: Settings = Depends(get_settings),
):
    try:
        ext = validate_audio_upload(file.filename, file.content_type)
    except UnsupportedAudioType as exc:
        raise HTTPException(status_code=415, detail="unsupported audio type") from exc

    upload_dir = resolve_api_path(settings.UPLOAD_DIR)
    try:
        tmp_path, size, digest = await save_upload_stream(
            file, upload_dir, settings.MAX_AUDIO_BYTES
        )
    except AudioTooLarge as exc:
        detail = f"audio file too large (max {format_size(settings.MAX_AUDIO_BYTES)})"
        raise HTTPException(status_code=413, detail=detail) from exc
    except EmptyUpload as exc:
        raise HTTPException(status_code=422, detail="audio file is empty") from exc

    # Name the file after the answer so a file exists only for a real answer.
    answer_id = str(uuid.uuid4())
    filename = f"{answer_id}{ext}"
    try:
        os.replace(tmp_path, upload_dir / filename)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise

    try:
        with _domain_errors():
            result = record_answer(
                db,
                candidate,
                question_id,
                kind=AnswerKind.AUDIO,
                content_sha256=digest,
                answer_id=answer_id,
                audio=AudioMeta(path=filename, content_type=file.content_type, size=size),
            )
    except Exception:
        (upload_dir / filename).unlink(missing_ok=True)
        raise

    if not result.created:
        # Replay: the stored file belongs to the earlier answer, drop ours.
        (upload_dir / filename).unlink(missing_ok=True)
        response.status_code = 200
    return _receipt(result.answer)
