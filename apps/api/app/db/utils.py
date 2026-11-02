import os


def ensure_sqlite_dir(url: str) -> None:
    """Create the parent directory for a file-backed SQLite URL.

    SQLite will not create missing directories, so both the app engine and
    Alembic (which builds its own engine in migrations/env.py) must call this
    before connecting.
    """
    if url.startswith("sqlite:///"):
        db_path = url.removeprefix("sqlite:///")
        if db_path != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
