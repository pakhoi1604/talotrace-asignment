---
phase: 4
title: "Verification + docs"
status: done
priority: P1
dependencies: [3]
---

# Phase 4: Verification + docs

## Overview
Prove the candidate flow end-to-end against the real API with seeded links. Then update the user-facing docs. There is no FE unit-test framework (out of scope), so verification = gates + a scripted browser smoke.

## Requirements
- Functional: every acceptance criterion in `plan.md` is checked against a running `make dev` + `make seed`.
- Non-functional: `make lint && make test` green; `pnpm build` green.

## Smoke script (agent-browser or manual, with `make dev` running)
<!-- Updated: Validation Session 1 - branch step, friendly copy + MIME checks -->
0. (Before phase 1, not at verify time) backend committed on `feat/candidate-api-db-seed`; FE work on `feat/candidate-interview-fe` branched from it.
1. `make seed` → pick candidate A (fewest answers) and candidate B from `apps/api/data/candidate-links.csv`.
2. Open A's link: header shows role + first name + "{n} answers saved"; progress highlights the right segments; question text = current question.
3. Type an answer, reload before submitting → draft restored.
4. Submit → receipt "Typed answer received at HH:MM"; header count +1.
5. "Back to this question" → text prefilled → edit → submit → receipt (replacement). "Next question →" → next question.
6. Upload tab: drop a small `.m4a` from `business-systems-pack/` → submit → "Audio file received at …".
7. Pick a `.txt` file → blocked client-side. Pick a > 25 MB file → blocked client-side. Then bypass the client checks (devtools) → server 415/413 shown in **friendly copy** (not `unsupported audio type`). Submit empty text via devtools → "Please write an answer before submitting."
7b. Console: `withAudioMime(new File(["x"], "a.m4a", { type: "" })).type === "audio/mp4"`. Upload a pack `.m4a`; Network tab shows the part's Content-Type as `audio/*`.
8. Upload a ~20 MB valid audio file through the rewrite → success. If not, raise the Next proxy body limit (phase 2 risk).
9. Answer forward to the last question → receipt shows completion, no back button; reload → completed screen.
10. Rerun `make seed` → A's old link → "This link isn't valid".
11. `curl -I localhost:3000/i/<token>` → `Referrer-Policy: no-referrer`, `X-Robots-Tag: noindex`.
12. Network tab: no response contains score/rubric/job fields. Token only in the `Authorization` header.
13. Resize to 360px → no horizontal scroll.

## Docs
- `README.md`: "Candidate interview" section: run `make seed`, open a printed `/i/<token>` link, MOCK email note.
- `docs/architecture.md`: short "Frontend" note: candidate page is client-rendered against `/api/candidate/*` with a Bearer token from the URL; Referrer-Policy; tokens in `globals.css` (see `docs/design-guidelines.md`).
- `docs/architecture.md` "What we chose not to build": add previous-question navigation and in-browser mic recording.
- `docs/design-guidelines.md`: confirm it matches the shipped tokens.

## Related Code Files
- Modify: `README.md`, `docs/architecture.md`, `docs/design-guidelines.md` (if it drifted)
- Possibly modify: `apps/web/next.config.ts` (body-size limit)

## Implementation Steps
1. Run the smoke script; fix defects in phase 3 files.
2. `make lint && make test && (cd apps/web && pnpm build)`.
3. Update docs.

## Success Criteria
- [x] All smoke steps (0–13, incl. 7b) pass
- [x] Gates green
- [x] README + architecture updated

## Risk Assessment
- The seed rotates tokens on every run, so re-copy links after reseeding.
- Audio smoke depends on the `.m4a` files in the data pack. Do not modify the pack (read-only).
