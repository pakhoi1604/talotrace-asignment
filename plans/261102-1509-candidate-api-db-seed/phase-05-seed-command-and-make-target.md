---
phase: 5
title: "Seed command + make seed"
status: done
priority: P1
dependencies: [3]
---

# Phase 5: Seed command + `make seed`

## Overview
`make seed` loads the data pack (questions, roles, candidates, 35 answers incl. 5 audio) into SQLite through the same submission service as the API, queues their scoring jobs, rotates every candidate's token, and prints and saves access links.

## Requirements
- Functional: idempotent data load; latest-wins applied to pack duplicates (A022 → superseded, A023 → current); audio copied into `UPLOAD_DIR`; all tokens rotated each run; links printed + written to CSV.
- Non-functional: fails fast with a clear message on bad or missing pack data; never modifies `business-systems-pack/`; output labelled **MOCK email**.

## Architecture

```
business-systems-pack/
  questions.md ──► parse roles ("Open roles:" line) + Q1–Q6 + rubric 1–4
  pipeline_log.csv ─► name/email by candidate_id
  answers/*.json (+ .m4a) ─► candidates (distinct candidate_id+role) + answers
                         │
                         ▼ sorted by submitted_at
              record_answer(enforce_rules=False, answer_id=pack id, submitted_at=pack ts)
                         │  (answer + queued job, one tx each; replay = skip)
                         ▼
              issue_token() for every candidate ─► stdout table + data/candidate-links.csv
```

Config additions (`app/core/config.py`):
- `DATA_PACK_DIR: str = "../../business-systems-pack"` (relative to `apps/api`)
- `WEB_BASE_URL: str = "http://localhost:3000"` → link = `{WEB_BASE_URL}/i/{token}`

Idempotency:
- roles/questions: upsert by title / id (update text + rubric if changed).
- candidates: upsert by id (update name/email/role).
- answers: skip if `db.get(Answer, pack_id)` exists; otherwise `record_answer`. Rerun → 0 new rows.
- tokens: always re-issued (user decision). Old links → 401.

Audio answers (`transcript: null`, `audio_file` set): copy to `UPLOAD_DIR/<answer_id>.m4a`, hash the bytes, `kind=audio`, content type `audio/mp4`. Transcript JSONs → `kind=text`, `text=transcript`.

Validation (abort with non-zero exit and nothing half-done for that step):
- exactly 6 questions, each with rubric keys 1–4
- every answer's `candidate_id` present in `pipeline_log.csv`; role in roles list; `question_id` in questions
- audio file exists when `transcript` is null; one of transcript/audio present

Output:
```
MOCK EMAIL: links are printed here instead of being emailed.
C2041  Backend Engineer   <name>   http://localhost:3000/i/<token>
...
Wrote 18 links to data/candidate-links.csv  (gitignored; tokens rotated, previous links revoked)
Loaded: 5 roles, 6 questions, 18 candidates, 35 answers (34 current), 35 scoring jobs (34 queued)
```

## Related Code Files
- Create: `apps/api/app/seed/__init__.py`
- Create: `apps/api/app/seed/runner.py`: `run_seed(session_factory, *, pack_dir, upload_dir, links_path, web_base_url) -> SeedSummary` (counts + links), no printing
- Create: `apps/api/app/seed/__main__.py`: thin CLI. Builds args from settings, calls `run_seed`, prints the table + summary (`python -m app.seed`), exits non-zero on `DataPackError`
- Create: `apps/api/app/seed/data_pack_parser.py`: pure parsers: `parse_questions_md`, `load_pipeline_people`, `load_pack_answers` → dataclasses; raises `DataPackError`
- Modify: `apps/api/app/core/config.py`: `DATA_PACK_DIR`, `WEB_BASE_URL`
- Modify: `apps/api/.env.example`: the two new vars
- Modify: `Makefile`: `seed: migrate` → `cd apps/api && uv run python -m app.seed`; add to `.PHONY`
- Modify: `README.md`: "Seed data" section (`make seed`, where links go, rotation, MOCK email)
- Modify: `AGENTS.md`: commands table row for `make seed`
- Tests already exist from phase 1: `tests/test_data_pack_parser.py`, `tests/test_seed.py`.

## Implementation Steps
1. Parser module with regexes: `^## (Q\d)\. (.+)$`, `^- \*\*(\d):\*\* (.+)$`, `^Open roles: (.+)\.$`. Make `test_data_pack_parser.py` green.
2. `run_seed`: upsert roles → questions → candidates; commit; import answers sorted by `(submitted_at, answer_id)` via `record_answer(enforce_rules=False)`; issue tokens; commit; write CSV (`candidate_id,name,role,link`) to `links_path`. Make `test_seed.py` green.
3. `__main__` CLI printing, Makefile target, docs.
4. Manual smoke: `make seed`, then `curl -H "Authorization: Bearer <token>" localhost:8000/api/candidate/interview`.

## Success Criteria
- [ ] `test_data_pack_parser.py` + `test_seed.py` green, with no test edits
- [ ] `make setup && make seed` works on a clean checkout and prints 18 links
- [ ] Opening a printed token via `GET /api/candidate/interview` (curl with Bearer) shows the right candidate + current question
- [ ] Full gate: `make lint && make test` green; `uv run alembic check` clean

## Risk Assessment
- Relative `DATA_PACK_DIR` breaks if run from another CWD → resolve relative to `apps/api` (`Path(__file__)`-based default), and make the error message print the resolved path.
- Rotating tokens mid-demo kills open candidate sessions → documented in README; intended.
- Pack timestamps are naive → treat as UTC (documented).
