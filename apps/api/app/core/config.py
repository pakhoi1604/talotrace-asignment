from functools import lru_cache
from pathlib import Path

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


@lru_cache
def get_settings() -> Settings:
    return Settings()
