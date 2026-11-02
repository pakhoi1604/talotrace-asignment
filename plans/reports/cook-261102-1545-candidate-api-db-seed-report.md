# Cook report: Candidate API + DB + `make seed`

- **Plan:** `plans/261102-1509-candidate-api-db-seed/` (5 phases, all done)
- **Branch:** `feat/candidate-api-db-seed` (new, per request)
- **Mode:** `--auto`, code mode (plan path input)

## What shipped

Backend-only candidate slice, test-first per plan:

- **Models + migration** — `roles`, `questions`, `candidates`, `answers`, `scoring_jobs`; named constraints; partial unique index `uq_answers_current (candidate_id, question_id) WHERE superseded_at IS NULL`. Autogen migration `7e042563977a`; `alembic check` clean.
- **Services** — `candidate_access` (sha256-only tokens, issue/lookup/rotate), `interview_progress`, `answer_submission` (replay → `created=False`; latest-wins supersede + job `superseded`; answer+job in one tx; IntegrityError race → replay/`ConcurrentSubmission`, non-index integrity errors re-raised).
- **API** — `GET /api/candidate/interview`, `PUT /api/candidate/answers/{qid}` (201/200), `PUT .../audio` (streamed, capped, hashed). Uniform 401; custom 422 handler → `{"detail": "<field>: <msg>"}`; leak-proof Pydantic DTOs.
- **Seed** — `parse_questions_md`/`load_pipeline_people`/`load_pack_answers` (`DataPackError` on all bad input), `run_seed` (idempotent upserts, answers via `record_answer(enforce_rules=False)` → A022 superseded/A023 current, token rotation, CSV to `apps/api/data/candidate-links.csv`), `python -m app.seed` CLI prints 18 links labelled MOCK EMAIL. `make seed` target added.
- **Docs** — `docs/api-doc.md` (3 sections: auth/request/response-per-code/errors tables with exact `detail`s), `docs/architecture.md` (data model + lifecycle), `api-types.ts` mirror, README + AGENTS.md.

## Gates

- `make test` — **59 passed**
- `make lint` — green (ruff + biome + tsc)
- `uv run alembic check` — no drift
- Live smoke — uvicorn + curl: seeded token → 200 interview view; bad token → 401; PUT → 201; replay → 200 same `answer_id`
- `code-reviewer` subagent — CHANGES-NEEDED → all SHOULD-FIX applied (below)
- `tester` subagent — static pass on all criteria; runtime verified by gates above

## Review findings → resolution

| Finding | Resolution |
|---|---|
| `person.role` could KeyError instead of `DataPackError` | Validate pipeline role in `roles_by_title` → `DataPackError` |
| Parser `KeyError`s on missing `submitted_at` / malformed CSV | Wrapped → `DataPackError` |
| `IntegrityError` catch could mask non-race bugs | Re-raise when reload finds no current answer |
| `UPLOAD_DIR` resolved differently in seed vs route | Shared `resolve_api_path()` in `config.py` (relative → `apps/api`) |
| Seed/route file orphans on error/replay | `unlink` on every non-commit path; `os.replace` guarded |
| Doc test didn't enforce `detail` strings | `EXPECTED_DETAILS` asserted per section |
| 401 variants only on GET | Parametrized all 3 endpoints × 4 bad-auth cases + rotated |
| Missing `MAX_AUDIO_BYTES` boundary test | Added (exactly 1024 B → 201) |
| Audio 404/409 leaves-no-file untested | Added `test_audio_domain_rejection_leaves_no_file` |
| Rejected: blank transcript → `DataPackError` | Reverted — real pack has `A007` with `transcript: ""` (must seed) |

## Notes

- Starlette 1.10 keeps `include_router` mounts as `_IncludedRouter`; doc-coverage test traverses `original_router` — plan-compatible.
- Dev DB reseeded clean after smoke: 35 answers (34 current), 35 jobs (34 queued).
- `migrations/versions/` excluded from ruff (generated code).
- Not committed by workflow: untracked `docs/design/`, `plans/261102-1529-*` (other session's work).

## Unresolved questions

None.
