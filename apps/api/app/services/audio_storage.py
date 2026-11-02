import hashlib
import uuid
from pathlib import Path

from fastapi import UploadFile

from app.services.answer_submission import AUDIO_HASH_PREFIX

ALLOWED_EXTENSIONS = {".m4a", ".mp3", ".wav", ".webm", ".ogg", ".mp4"}
# Browser recorders may label audio-only files as video/*.
ALLOWED_CONTENT_TYPES = {"video/mp4", "video/webm"}

_CHUNK = 1024 * 1024


class UnsupportedAudioType(Exception):
    pass


class AudioTooLarge(Exception):
    pass


class EmptyUpload(Exception):
    pass


def validate_audio_upload(filename: str | None, content_type: str | None) -> str:
    """Check the allow-list; return the file extension to keep."""
    ext = Path(filename or "").suffix.lower()
    ctype = (content_type or "").lower()
    type_ok = ctype.startswith("audio/") or ctype in ALLOWED_CONTENT_TYPES
    if ext not in ALLOWED_EXTENSIONS or not type_ok:
        raise UnsupportedAudioType
    return ext


def format_size(num_bytes: int) -> str:
    if num_bytes % (1024 * 1024) == 0:
        return f"{num_bytes // (1024 * 1024)} MB"
    if num_bytes % 1024 == 0:
        return f"{num_bytes // 1024} KB"
    return f"{num_bytes} B"


async def save_upload_stream(
    upload: UploadFile, upload_dir: Path, max_bytes: int
) -> tuple[Path, int, str]:
    """Stream an upload to a temp file, hashing and capping as it goes.

    Returns (tmp_path, size, content_sha256). Caller renames on success.
    """
    upload_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = upload_dir / f"tmp-{uuid.uuid4()}"
    hasher = hashlib.sha256(AUDIO_HASH_PREFIX)
    size = 0
    try:
        with tmp_path.open("wb") as out:
            while chunk := await upload.read(_CHUNK):
                size += len(chunk)
                if size > max_bytes:
                    raise AudioTooLarge
                hasher.update(chunk)
                out.write(chunk)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise
    if size == 0:
        tmp_path.unlink(missing_ok=True)
        raise EmptyUpload
    return tmp_path, size, hasher.hexdigest()
