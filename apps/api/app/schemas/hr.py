from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import UtcDatetime


class HrSignIn(BaseModel):
    email: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=255)


class HrSessionView(BaseModel):
    email: str
    expires_at: UtcDatetime


class RoleRef(BaseModel):
    id: int
    title: str


class JobCounts(BaseModel):
    """Counts over current answers' jobs; superseded jobs are never counted."""

    queued: int = 0
    running: int = 0
    scored: int = 0
    failed: int = 0
    needs_person: int = 0


class AllJobCounts(JobCounts):
    superseded: int = 0


class RoleSummary(BaseModel):
    id: int
    title: str
    candidate_count: int
    job_counts: JobCounts


class RoleList(BaseModel):
    roles: list[RoleSummary]


class CandidateRow(BaseModel):
    id: str
    name: str
    answered_count: int
    total_questions: int
    avg_suggested: float | None
    avg_final: float | None
    job_counts: JobCounts
    last_activity_at: UtcDatetime | None


class RoleCandidates(BaseModel):
    role: RoleRef
    total_questions: int
    candidates: list[CandidateRow]


class AudioMeta(BaseModel):
    content_type: str | None
    size_bytes: int
    url: str


class JobView(BaseModel):
    id: int
    status: str
    attempts: int
    last_error: str | None
    suggested_score: int | None
    suggested_reason: str | None
    needs_person_reason: str | None
    model: str | None
    updated_at: UtcDatetime


class DecisionView(BaseModel):
    id: int
    answer_id: str
    kind: str
    score: int
    reason: str | None
    hr_email: str
    created_at: UtcDatetime


class EarlierSubmission(BaseModel):
    id: str
    kind: str
    text: str | None
    audio: AudioMeta | None
    submitted_at: UtcDatetime
    superseded_at: UtcDatetime | None
    decisions: list[DecisionView]


class AnswerReview(BaseModel):
    id: str
    kind: str
    text: str | None
    audio: AudioMeta | None
    submitted_at: UtcDatetime
    submission_count: int
    job: JobView | None
    final_score: int | None
    final_source: Literal["hr", "suggested"] | None
    decisions: list[DecisionView]
    earlier_submissions: list[EarlierSubmission]


class QuestionRef(BaseModel):
    id: str
    position: int
    text: str
    rubric: dict


class QuestionReview(BaseModel):
    question: QuestionRef
    answer: AnswerReview | None


class CandidateReview(BaseModel):
    id: str
    name: str
    email: str
    role: RoleRef
    total_questions: int
    answered_count: int
    avg_suggested: float | None
    avg_final: float | None
    job_counts: JobCounts
    questions: list[QuestionReview]


class JobAnswerRef(BaseModel):
    id: str
    kind: str
    question_id: str


class JobCandidateRef(BaseModel):
    id: str
    name: str


class JobListItem(BaseModel):
    id: int
    status: str
    attempts: int
    last_error: str | None
    needs_person_reason: str | None
    updated_at: UtcDatetime
    answer: JobAnswerRef
    candidate: JobCandidateRef
    role: RoleRef


class JobList(BaseModel):
    counts: AllJobCounts
    jobs: list[JobListItem]


class OverrideRequest(BaseModel):
    score: int = Field(ge=1, le=4)
    reason: str

    @field_validator("reason")
    @classmethod
    def _validate_reason(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        if len(value) > 2000:
            raise ValueError("must be at most 2000 characters")
        return value


class AcceptRequest(BaseModel):
    score: int = Field(ge=1, le=4)


class RetryRequest(BaseModel):
    """Explicit empty body — the endpoint still requires a JSON content type."""

    model_config = {"extra": "ignore"}
