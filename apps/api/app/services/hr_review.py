"""HR review queries and assembly. No FastAPI imports."""

from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models import Answer, Candidate, Question, Role, ScoringJob
from app.models.enums import JobStatus
from app.schemas.hr import (
    AllJobCounts,
    AnswerReview,
    AudioMeta,
    CandidateReview,
    CandidateRow,
    DecisionView,
    EarlierSubmission,
    JobAnswerRef,
    JobCandidateRef,
    JobCounts,
    JobList,
    JobListItem,
    JobView,
    QuestionRef,
    QuestionReview,
    RoleCandidates,
    RoleRef,
    RoleSummary,
)

# Server-chosen response content types for audio playback, keyed by file
# extension. The stored upload header is candidate-controlled and never used.
AUDIO_CONTENT_TYPES = {
    ".m4a": "audio/mp4",
    ".mp4": "audio/mp4",
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".webm": "audio/webm",
    ".ogg": "audio/ogg",
}

_COUNTED = (
    JobStatus.QUEUED,
    JobStatus.RUNNING,
    JobStatus.SCORED,
    JobStatus.FAILED,
    JobStatus.NEEDS_PERSON,
)


def visible_suggestion(job: ScoringJob | None) -> tuple[int | None, str | None]:
    """Read-side gate: only scored/needs_person jobs expose a suggestion.

    A bad row written by raw SQL, a bulk update, or a buggy worker can never
    surface a score for a job that isn't scored/needs_person.
    """
    if job is None or job.status not in (JobStatus.SCORED, JobStatus.NEEDS_PERSON):
        return None, None
    return job.suggested_score, job.suggested_reason


def final_score(answer: Answer) -> tuple[int | None, str | None]:
    """Newest HR decision wins; else the suggestion of a scored job."""
    if answer.decisions:
        return answer.decisions[0].score, "hr"
    if answer.job is not None and answer.job.status == JobStatus.SCORED:
        score, _ = visible_suggestion(answer.job)
        if score is not None:
            return score, "suggested"
    return None, None


def _mean(scores: list[int]) -> float | None:
    return round(sum(scores) / len(scores), 2) if scores else None


def _job_counts(answers: list[Answer]) -> JobCounts:
    counts = dict.fromkeys((s.value for s in _COUNTED), 0)
    for answer in answers:
        job = answer.job
        if job is not None and job.status in counts:
            counts[job.status] += 1
    return JobCounts(**counts)


def _current_answers(candidate: Candidate) -> list[Answer]:
    return [a for a in candidate.answers if a.superseded_at is None]


def _averages(answers: list[Answer]) -> tuple[float | None, float | None]:
    suggested = []
    finals = []
    for answer in answers:
        job = answer.job
        # avg_suggested counts `scored` only — a needs_person score is one
        # the model didn't trust, so it stays out of the average.
        if job is not None and job.status == JobStatus.SCORED:
            score, _ = visible_suggestion(job)
            if score is not None:
                suggested.append(score)
        score, _ = final_score(answer)
        if score is not None:
            finals.append(score)
    return _mean(suggested), _mean(finals)


def _last_activity_at(candidate: Candidate):
    submitted = [a.submitted_at for a in candidate.answers]
    return max(submitted) if submitted else None


def _audio_meta(answer: Answer) -> AudioMeta | None:
    if answer.audio_path is None:
        return None
    content_type = AUDIO_CONTENT_TYPES.get(Path(answer.audio_path).suffix.lower())
    return AudioMeta(
        content_type=content_type,
        size_bytes=answer.audio_size_bytes or 0,
        url=f"/api/hr/answers/{answer.id}/audio",
    )


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


def _job_view(job: ScoringJob | None) -> JobView | None:
    if job is None:
        return None
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


def _answer_review(answer: Answer, earlier: list[Answer]) -> AnswerReview:
    score, source = final_score(answer)
    return AnswerReview(
        id=answer.id,
        kind=answer.kind,
        text=answer.text,
        audio=_audio_meta(answer),
        submitted_at=answer.submitted_at,
        submission_count=len(earlier) + 1,
        job=_job_view(answer.job),
        final_score=score,
        final_source=source,
        decisions=[_decision_view(d) for d in answer.decisions],
        earlier_submissions=[
            EarlierSubmission(
                id=old.id,
                kind=old.kind,
                text=old.text,
                audio=_audio_meta(old),
                submitted_at=old.submitted_at,
                superseded_at=old.superseded_at,
                decisions=[_decision_view(d) for d in old.decisions],
            )
            for old in earlier
        ],
    )


def _load_candidates(db: Session, stmt):
    return db.scalars(
        stmt.options(
            selectinload(Candidate.answers).selectinload(Answer.job),
            selectinload(Candidate.answers).selectinload(Answer.decisions),
        )
    ).all()


def _candidate_row(candidate: Candidate, total_questions: int) -> CandidateRow:
    current = _current_answers(candidate)
    avg_suggested, avg_final = _averages(current)
    return CandidateRow(
        id=candidate.id,
        name=candidate.name,
        answered_count=len(current),
        total_questions=total_questions,
        avg_suggested=avg_suggested,
        avg_final=avg_final,
        job_counts=_job_counts(current),
        last_activity_at=_last_activity_at(candidate),
    )


def _total_questions(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(Question)) or 0


def list_roles(db: Session) -> list[RoleSummary]:
    roles = db.scalars(
        select(Role).options(
            selectinload(Role.candidates).selectinload(Candidate.answers).selectinload(Answer.job)
        )
    ).all()
    summaries = []
    for role in roles:
        answers = [a for c in role.candidates for a in _current_answers(c)]
        summaries.append(
            RoleSummary(
                id=role.id,
                title=role.title,
                candidate_count=len(role.candidates),
                job_counts=_job_counts(answers),
            )
        )
    return sorted(summaries, key=lambda r: r.title)


def list_role_candidates(db: Session, role_id: int) -> RoleCandidates | None:
    role = db.get(Role, role_id)
    if role is None:
        return None
    candidates = _load_candidates(db, select(Candidate).where(Candidate.role_id == role_id))
    total = _total_questions(db)
    return RoleCandidates(
        role=RoleRef(id=role.id, title=role.title),
        total_questions=total,
        candidates=sorted((_candidate_row(c, total) for c in candidates), key=lambda c: c.name),
    )


def get_candidate_review(db: Session, candidate_id: str) -> CandidateReview | None:
    candidates = _load_candidates(db, select(Candidate).where(Candidate.id == candidate_id))
    if not candidates:
        return None
    candidate = candidates[0]
    questions = db.scalars(select(Question).order_by(Question.position)).all()
    current_by_question = {a.question_id: a for a in candidate.answers if a.superseded_at is None}
    earlier_by_question: dict[str, list[Answer]] = {}
    for a in candidate.answers:
        if a.superseded_at is not None:
            earlier_by_question.setdefault(a.question_id, []).append(a)

    current = _current_answers(candidate)
    avg_suggested, avg_final = _averages(current)
    total = len(questions)
    return CandidateReview(
        id=candidate.id,
        name=candidate.name,
        email=candidate.email,
        role=RoleRef(id=candidate.role.id, title=candidate.role.title),
        total_questions=total,
        answered_count=len(current),
        avg_suggested=avg_suggested,
        avg_final=avg_final,
        job_counts=_job_counts(current),
        questions=[
            QuestionReview(
                question=QuestionRef(id=q.id, position=q.position, text=q.text, rubric=q.rubric),
                answer=(
                    _answer_review(
                        current_by_question[q.id],
                        sorted(
                            earlier_by_question.get(q.id, []),
                            key=lambda a: a.submitted_at,
                            reverse=True,
                        ),
                    )
                    if q.id in current_by_question
                    else None
                ),
            )
            for q in questions
        ],
    )


def list_jobs(db: Session, status: JobStatus | None) -> JobList:
    rows = db.execute(select(ScoringJob.status, func.count()).group_by(ScoringJob.status)).all()
    counts = {s.value: 0 for s in JobStatus}
    counts.update({row_status: n for row_status, n in rows})
    counts = AllJobCounts(**counts)

    stmt = select(ScoringJob).options(
        selectinload(ScoringJob.answer).selectinload(Answer.candidate).selectinload(Candidate.role)
    )
    if status is None:
        stmt = stmt.where(ScoringJob.status != JobStatus.SUPERSEDED)
    else:
        stmt = stmt.where(ScoringJob.status == status)
    stmt = stmt.order_by(ScoringJob.updated_at.desc(), ScoringJob.id.desc())

    items = []
    for job in db.scalars(stmt).all():
        answer = job.answer
        candidate = answer.candidate
        items.append(
            JobListItem(
                id=job.id,
                status=job.status,
                attempts=job.attempts,
                last_error=job.last_error,
                needs_person_reason=job.needs_person_reason,
                updated_at=job.updated_at,
                answer=JobAnswerRef(id=answer.id, kind=answer.kind, question_id=answer.question_id),
                candidate=JobCandidateRef(id=candidate.id, name=candidate.name),
                role=RoleRef(id=candidate.role.id, title=candidate.role.title),
            )
        )
    return JobList(counts=counts, jobs=items)
