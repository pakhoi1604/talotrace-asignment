from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# apps/api root — relative settings paths resolve against this, not the CWD.
API_DIR = Path(__file__).resolve().parents[2]


def resolve_api_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else (API_DIR / path).resolve()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = "sqlite:///./data/app.db"
    GEMINI_API_KEY: str | None = None
    GEMINI_MODEL: str = "gemini-3.5-flash-lite"
    UPLOAD_DIR: str = "./uploads"
    MAX_AUDIO_BYTES: int = 25 * 1024 * 1024
    # Resolved relative to apps/api when not absolute.
    DATA_PACK_DIR: str = "../../business-systems-pack"
    WEB_BASE_URL: str = "http://localhost:3000"
    # MOCK sign-in: the single HR account.
    HR_EMAIL: str | None = None
    HR_PASSWORD: str | None = None
    HR_SESSION_TTL_HOURS: int = 12
    HR_COOKIE_SECURE: bool = False
    # Scorer + worker (see app/scoring, app/worker).
    SCORER_MAX_CALLS: int = 3  # LLM calls per run
    SCORER_TIMEOUT_SECONDS: float = 30
    SCORER_BACKOFF_SECONDS: float = 2  # 2s, then 4s
    SCORER_MAX_OUTPUT_TOKENS: int = 512
    WORKER_MAX_CLAIMS: int = 3  # runs before a job is failed
    WORKER_POLL_SECONDS: float = 2
    WORKER_MIN_CALL_INTERVAL_SECONDS: float = 4
    WORKER_LEASE_SECONDS: int = 120
    WORKER_MAX_RATE_LIMIT_PAUSE_SECONDS: float = 300

    @field_validator("HR_EMAIL", "HR_PASSWORD", mode="before")
    @classmethod
    def _blank_means_unset(cls, value):
        # HR_PASSWORD= in .env means "not configured", not an empty password.
        if isinstance(value, str) and not value.strip():
            return None
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
