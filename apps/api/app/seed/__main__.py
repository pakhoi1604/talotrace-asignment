"""`python -m app.seed` — load the data pack and print candidate access links."""

import sys

from app.core.config import API_DIR, get_settings, resolve_api_path
from app.db.session import SessionLocal
from app.seed.data_pack_parser import DataPackError
from app.seed.runner import run_seed


def main() -> int:
    settings = get_settings()
    links_path = API_DIR / "data" / "candidate-links.csv"

    try:
        summary = run_seed(
            SessionLocal,
            pack_dir=resolve_api_path(settings.DATA_PACK_DIR),
            upload_dir=resolve_api_path(settings.UPLOAD_DIR),
            links_path=links_path,
            web_base_url=settings.WEB_BASE_URL,
        )
    except DataPackError as exc:
        print(f"seed failed: {exc}", file=sys.stderr)
        return 1

    print("MOCK EMAIL: links are printed here instead of being emailed.")
    width = max(len(link.role) for link in summary.links)
    for link in summary.links:
        print(f"{link.candidate_id}  {link.role:<{width}}  {link.name}  {link.link}")
    print(
        f"\nWrote {len(summary.links)} links to {links_path} "
        "(gitignored; tokens rotated, previous links revoked)"
    )
    print(
        f"Loaded: {summary.roles} roles, {summary.questions} questions, "
        f"{summary.candidates} candidates, {summary.answers} answers "
        f"({summary.answers_current} current), {summary.jobs} scoring jobs "
        f"({summary.jobs_queued} queued)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
