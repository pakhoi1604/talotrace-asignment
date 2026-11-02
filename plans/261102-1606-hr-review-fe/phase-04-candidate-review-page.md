---
phase: 4
title: "Candidate review"
status: completed
priority: P1
dependencies: [2]
---

# Phase 4: Candidate review

## Overview
`/hr/candidates/[candidateId]` faithful to `CandidateReview.dc.html`: candidate summary, then one card per question with the answer on the left and the score/decision panel on the right. HR can accept, override (reason required) and retry failed jobs. This is where the brief's "What must be true" items become visible: which submission counts, failed ≠ low score, flagged answers need a person.

## Requirements
- Functional
  - Summary: initials avatar, name, "{role} · {answered} of {total} answered · last answer {relative}", Avg suggested, Avg final (with HR), job count chips, back link "{role} · all candidates".
  - Per question (all `total_questions`, in `position` order): status chip (+ "HR override"/"HR accepted" chip), "Question {n} of {total}", question text, collapsible grading guide (rubric 1–4), answer (text or audio), "Submitted N× · this one counts", earlier submissions with their HR decisions, side panel by state (table below).
  - Actions: **Accept {n}** (only `scored` with a visible suggestion and no HR decision yet), **Override / Edit override** (any answered question), **Retry scoring** (only `failed`). One override form open at a time.
  - After every action: refetch the review. On 409: friendly message (phase 1 map) inside that card + refetch.
  <!-- Updated: Validation Session 1 - polling replaced by Refresh button; override on any answered question; grading guide kept -->
  - Refresh button in the summary card (no auto-refresh). Refresh and post-action refetches must not close an open override form or wipe a half-typed reason (form state lives in the screen, keyed by answer id; it's reset only on save/cancel or when that answer id disappears).
- Non-functional
  - The UI renders only what the API returns. A failed job shows **no number** in the score slot. Nothing is hard-coded.
  - Override form: `fieldset` + `legend` (sr-only) radio group, keyboard arrows work, visible focus ring on the chosen score; reason `Textarea` with `required`, `maxLength={2000}`, live count; Save disabled while pending or when reason is blank.
  - Cards are `<article aria-labelledby>`; the side panel stacks under the answer below ~900px (`flex-wrap`, as in the mockup).
  - Tokens only.

## Architecture

### Data
`useHrResource(() => getCandidateReview(id), [id])`; `RefreshButton` → `reload()`. 404 `candidate not found` → not-found card + link to `/hr`.

### Panel state (`src/lib/hr-review-state.ts`, pure)
```ts
type Panel =
  | { kind: "unanswered" }
  | { kind: "failed"; job: JobView }
  | { kind: "decided"; decision: DecisionView; suggested: number | null; reason: string | null; job: JobView }
  | { kind: "scored"; score: number; reason: string; job: JobView }
  | { kind: "needs_person"; reason: string | null; suggested: number | null; job: JobView }
  | { kind: "queued"; job: JobView };          // queued or running

panelFor(answer: AnswerReview | null): Panel
  // null → unanswered
  // final_source === "hr" (decisions[0] exists) → decided   (HR decision wins, whatever the job status)
  // job.status failed → failed
  // scored → scored; needs_person → needs_person; queued|running → queued
canAccept(answer) = panel.kind === "scored"
```
`decided` keeps the job so the chip still shows the real job status, and Retry still appears when that job is `failed`.

### Side panel by state (`score-side-panel.tsx`)
| Panel | Content | Card tone | Actions |
|---|---|---|---|
| unanswered | "Not answered yet" (`text-muted-foreground`) | default | none |
| queued | lucide `Clock` + "Scoring queued" + "attempt {n}" when > 0 + "Updated {time}" | default | Override (secondary) |
| scored | `ScoreFigure` "{n} / 4 suggested"; label "Reason" + reason | default | **Accept {n}** (primary) · Override (secondary) |
| needs_person | `ScoreFigure` only if `suggested != null`; label "Why a person is needed" (`text-warning-ink`) + `needs_person_reason` | side `bg-warning-soft border-warning-border`, card `border-warning-border` | Override (primary) |
| failed | lucide `CircleAlert` + "No score yet" (`text-danger-ink font-bold`); `last_error`; "{attempts} attempt(s) made"; "Last attempt {time} · job #{id}" (`text-danger-ink-strong text-caption`) | side `bg-danger-soft border-danger-border`, card `border-danger-border` | **Retry scoring** (primary, lucide `RotateCw`) · Override (secondary) |
| decided | `ScoreFigure tone="hr"` "{final} / 4 final" + struck "{suggested} suggested" when a suggestion exists; label "Suggested reason" + reason (if any); HR box `bg-primary-soft rounded-md p-3`: label `text-primary-ink` "HR reason · {hr_email} · {time}" (accept: "Accepted by {hr_email} · {time}") + reason; `<details>` "Earlier HR decisions ({n})" for `decisions[1..]` | default | Edit override (secondary); Retry scoring if the job is `failed` |

Override form open → card `border-primary-muted shadow-focus` and the form replaces the action row.

### Override form (`override-form.tsx`)
Card `rounded-lg border-primary-border bg-card p-4`; title "Override score"; 4 radio tiles `h-11 flex-1 rounded-tab border-input font-semibold`, checked `border-2 border-primary bg-primary-soft text-primary-strong font-bold` (radio input `sr-only`, the label is the tile); preselected = current final or suggested score, else none; "Reason (required)" with `text-danger`; `Textarea rows={3} text-meta`; Cancel (secondary) / Save override (primary). Client check: score chosen + reason trimmed non-blank → else inline message, no request. Submit `overrideScore(answer.id, score, reason.trim())` → close + refetch.

### Answer column (`answer-content.tsx`)
- Text: meta row lucide `AlignLeft` "Typed answer · received {HH:MM}"; body `text-body-sm leading-[1.65] text-foreground-body whitespace-pre-wrap max-w-[70ch]`.
- `submission_count > 1`: pill `bg-primary-soft text-primary-ink font-semibold` "Submitted {n}× · this one counts".
- Audio (`audio-answer-player.tsx`): panel `bg-muted rounded-lg p-3.5`; "Audio answer arrived · {audioFormatLabel} · {formatBytes}" + received time; native `<audio controls preload="none" src={audio.url} className="w-full">`; below it `Badge variant="warning"` **"Transcription not built"** + "Listen to score this answer manually (Override)."
- Earlier submissions (`earlier-submissions.tsx`): `<details>` summary `text-primary-strong font-medium` "Show earlier submission ({time}, replaced)" or "Show {n} earlier submissions"; each item: kind + received time + "replaced {time}"; text body or audio player; its decisions as compact HR notes ("HR override 3 · reason · email · time"). Copy: "Kept for the record. It doesn't count and has no score."
- Grading guide: `<details>` "Grading guide" under the question text → `<dl>` 1–4 with rubric text (`text-meta`).

### Components (`src/components/hr/review/`)
| File | Responsibility |
|---|---|
| `candidate-review-screen.tsx` | client root: data, `openOverrideFor: string | null`, `pendingAction`, per-card error map, action handlers (`accept`, `override`, `retry`) with 401/409 handling |
| `candidate-summary-card.tsx` | back link + summary section (`rounded-2xl border bg-card p-6 flex flex-wrap justify-between gap-6`); "Avg final (with HR)" number in `text-primary-strong`; "—" for null averages; `RefreshButton` |
| `question-review-card.tsx` | `<article>` shell `rounded-2xl border bg-card flex flex-wrap overflow-hidden`; left `flex-[999_1_520px] p-6 gap-3`; right `flex-[1_1_340px] p-6 bg-surface-subtle border-l gap-3.5`; eyebrow `text-caption font-bold uppercase tracking-[.05em] text-primary-strong`; question `text-body-lg font-semibold`; tone from panel |
| `answer-content.tsx`, `audio-answer-player.tsx`, `earlier-submissions.tsx`, `grading-guide.tsx` | left column pieces |
| `score-side-panel.tsx`, `override-form.tsx`, `hr-decision-note.tsx` | right column pieces |

## Related Code Files
- Create: `apps/web/src/app/hr/(app)/candidates/[candidateId]/page.tsx` (`metadata.title = "Review"`)
- Create: `apps/web/src/lib/hr-review-state.ts`
- Create: `apps/web/src/components/hr/review/*.tsx` (files above)

## Implementation Steps
<!-- Updated: user request 2026-11-02 - inspect design + map colors to tokens -->
0. **Inspect + map colors first.** Open `CandidateReview.dc.html`, list every color in the part you're building, and map each one to its token with the [color map](phase-01-gate-and-hr-api-client-plumbing.md#design-color--token-map). Code uses token utilities only: no hex, `rgb(a)`, `hsl`, `bg-[#…]` or inline color styles. Pick by role where one value maps to several tokens. Expected tokens: card, border, surface-subtle, muted, foreground, foreground-body, muted-foreground, input, primary, primary-strong, primary-ink, primary-muted, primary-border, primary-subtle, primary-soft, success-*, neutral-*, warning-soft/subtle/border/ink, danger-soft/subtle/border/ink/ink-strong, danger, shadow-focus.
1. `hr-review-state.ts` (`panelFor`, `canAccept`).
2. Read-only rendering: summary, cards, answer column, side panel states.
3. Actions: accept, retry, override form; per-card error + refetch; one-form-open rule; the form survives refetches.
4. Responsive + keyboard pass (tab order: answer → actions → form).
5. `pnpm lint && pnpm typecheck && pnpm build`.
6. Browser smoke (needs seeded data; force states with the API):
   - queued (default after seed), override a queued answer → decided
   - set a job to `failed` with `sqlite3` (read-only use of the dev DB, no code change) → "No score yet" + Retry → back to queued
   - accept on a scored answer (after the worker lands or via `sqlite3`)
   - candidate resubmits via `/i/{token}` → "Submitted 2× · this one counts" + earlier submission with its HR decision
   - audio answer plays (check a `Range` request works through the Next rewrite)

## Success Criteria
- [ ] Every color in this phase's UI traces to a token in the color map; `grep` finds no hex/rgb/hsl/arbitrary color in the files created here
- [ ] Every panel state in the table renders with the mockup's tone and spacing
- [ ] Failed job: no score number anywhere on the card; Retry → job back to queued after refetch
- [ ] Accept only visible for `scored` without an HR decision; never on `needs_person`
- [ ] Override without a reason is blocked client-side; with one → decided panel shows HR reason, email and time; history kept under "Earlier HR decisions"
- [ ] 409 responses show the friendly message and the card refreshes
- [ ] Audio answers show "Audio answer arrived", play, and carry the "Transcription not built" label
- [ ] Refresh updates job states; an open override form keeps its score and reason across a refresh
- [ ] Override is offered on every answered question (queued, failed, scored, needs a person, decided); collapsed grading guide shows rubric 1–4

## Risk Assessment
- Range/streaming through the Next rewrite: if seeking fails, the player still plays from the start (acceptable); note it. Don't add a Next route handler to proxy audio unless playback fails outright.
- Large component tree: keep each file < 200 lines; `candidate-review-screen.tsx` holds only orchestration.
- Race: HR acts while the worker scores → API 409s are mapped and the card refetches; nothing else needed client-side.
