from enum import StrEnum


class AnswerKind(StrEnum):
    TEXT = "text"
    AUDIO = "audio"


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SCORED = "scored"
    FAILED = "failed"
    NEEDS_PERSON = "needs_person"
    SUPERSEDED = "superseded"


class DecisionKind(StrEnum):
    OVERRIDE = "override"
    ACCEPT = "accept"
