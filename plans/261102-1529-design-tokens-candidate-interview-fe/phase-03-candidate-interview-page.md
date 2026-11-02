---
phase: 3
title: "Candidate interview page"
status: done
priority: P1
dependencies: [2]
---

# Phase 3: Candidate interview page

## Overview
Build `/i/[token]` faithful to `docs/design/interview [token] — Candidate-html/Interview.dc.html`, using phase 1 tokens and phase 2 client. One question at a time, typed or audio answer, instant receipt, resume on reload.

## Requirements
- Functional
  - Load: fetch `InterviewView`. Route to one of the states: invalid link · completed · answering · receipt.
  - Answer by typing (textarea, local draft) or uploading audio (click or drag-drop, single file).
  - Submit → receipt with kind + local time from `received_at` → "Next question →" refetches and shows the new current question.
  - "Back to this question" (only when the interview is not completed) reopens the just-submitted question with the typed text prefilled; resubmitting replaces the answer.
  - Last question submitted (`completed` after refetch) → receipt with a completion message, no back button.
- Non-functional
  - No score/grade/job status anywhere (the API has none; never hard-code any).
  - Token only in the URL path and the `Authorization` header. `Referrer-Policy: no-referrer`, `noindex`.
  - Responsive down to 360px. Keyboard-operable tabs and dropzone. `role="status"` on the receipt. Visible focus.
  - Candidate components use tokens only (no raw hex).

## Architecture

### Route
```
src/app/i/[token]/page.tsx   server component: metadata + <InterviewScreen />
```
- `export const metadata = { title: "Your interview", robots: { index: false, follow: false } }`.
- `InterviewScreen` is a client component that reads the token with `useParams<{ token: string }>()`. All data fetching is client-side, so there is no server fetch with `cacheComponents` and no token in server logs.
- `next.config.ts`: add `headers()` → `{ source: "/i/:path*", headers: [Referrer-Policy: no-referrer, X-Robots-Tag: noindex] }`.

### State machine (`useReducer` in `interview-screen.tsx`)
```
loading ──GET ok──► ready(view, screen)
   │                    screen = completed (view.completed)
   │                           | answer(question = view.current_question)
   ├──401──► invalid
   └──other/network──► loadError (message + "Reload" button)

answer ──submit ok──► receipt(question, receipt, text?)  + background refetch → view
receipt ──"Next question →"──► answer(view.current_question) | completed
receipt ──"Back to this question"──► answer(question, prefill=text)   [hidden if view.completed]
answer ──submit 409──► refetch view, inline alert (friendly copy)
answer ──submit 413/415/422/404──► inline alert (friendly copy), form kept
answer ──network error──► inline alert "Couldn't reach the server. Your draft is still on this device."
```

<!-- Updated: Validation Session 1 - friendly error copy map -->
### Friendly error copy (`src/lib/candidate-error-messages.ts`)
`toCandidateMessage(err: unknown): string`. Look up by documented `detail` string (phase 2 lists them), then fall back by status, then fall back to the raw `detail`:
| API `detail` | Candidate sees |
|---|---|
| `answer the current question first` | "This question isn't open yet. We've taken you back to your current question." (+ refetch) |
| `interview is closed` | "Your interview is already complete, so answers can't be changed." (+ refetch → completed) |
| `another submission for this question is in progress, please retry` | "We're still saving another answer to this question. Please try again in a moment." |
| `question not found` | "This question is no longer available. Please reload the page." |
| `text: must not be blank` | "Please write an answer before submitting." |
| `text: must be at most 10000 characters` | "Your answer is too long. Please keep it under 10,000 characters." |
| `audio file too large (max 25 MB)` | "That file is larger than 25 MB. Please upload a shorter recording." |
| `unsupported audio type` | "That file type isn't supported. Please use MP3, M4A, WAV, WebM, OGG or MP4." |
| `audio file is empty` / `file: Field required` | "Please choose an audio file before submitting." |
| status 401 (any) | → invalid-link screen (not an inline alert) |
| network / `TypeError` | "Couldn't reach the server. Your draft is still on this device." |
Submit is disabled while pending, which prevents double submits. The server is idempotent anyway (identical replay → 200, same receipt).

### Component tree (`src/components/interview/`, kebab-case)
| File | Responsibility | Design ref |
|---|---|---|
| `interview-screen.tsx` | client root, reducer, fetch/submit orchestration | whole artboard |
| `interview-header.tsx` | logo tile (`bg-primary rounded-sm size-8`, lucide `Check`), title `{role} interview`, subtitle `Hi {firstName} — your progress saves automatically`, `Badge variant="success"` "{n} answer(s) saved" (hidden when 0) | `<header>` |
| `interview-progress.tsx` | "Question {position} of {total}" (`text-primary-strong`) + "{answered_count} of {total} answered"; 6-segment grid: answered positions `bg-primary`, displayed position `bg-primary-muted`, rest `bg-border`; `aria-hidden` on segments | progress block |
| `answer-form.tsx` | heading, segmented tabs, active field, inline error alert, submit row (right-aligned `Button size="xl"` "Submit answer" / "Sending…") | `notSubmitted` branch |
| `text-answer-field.tsx` | `Label` "Your answer" + `Textarea rows={9}` + helper "Draft saved on this device"; shows a char-limit error past `MAX_TEXT_CHARS` | text branch |
| `audio-answer-dropzone.tsx` | `<label>` dashed `border-2 border-primary-muted bg-dropzone rounded-xl py-9 px-5`, mic bubble `size-12 rounded-full bg-primary-subtle` (lucide `Mic`), "Drop an audio file or **browse**", "MP3, M4A, WAV or WebM · up to 25 MB"; `sr-only` input `accept="audio/*,.m4a,.mp3,.wav,.webm,.ogg,.mp4"`; dragover state `border-primary bg-primary-soft`; `focus-within` ring; selected-file row (name, size, "Remove"); client checks extension + size | audio branch |
| `answer-receipt.tsx` | `Alert variant="success" role="status"`: check bubble `size-9 rounded-full bg-success`, title "Your answer arrived" (`text-body-lg font-bold text-success-ink-strong`), body "{Typed answer\|Audio file} received at {HH:MM}. Saved safely — you can close this page and come back with the same link."; actions: `Button variant="secondary" size="cta"` "Back to this question" + `Button size="xl"` "Next question →"; completed variant: "That was the last question — all {total} answers are saved." | `submitted` branch |
| `interview-message-card.tsx` | shared card for invalid link ("This link isn't valid": ask HR for a new link), load error, and completed ("You're all done", list of answered positions + kind + time) | (new states, same card recipe) |

Card recipe (from the design): `rounded-3xl border bg-card p-6 sm:p-8 shadow-card flex flex-col gap-6`. Page: `min-h-full bg-background`; header `bg-card border-b`; inner `mx-auto max-w-interview px-6 py-4`; main `mx-auto max-w-interview px-6 pt-8 pb-16 flex flex-col gap-6`. Question heading: `text-heading font-bold`.

Segmented tabs: `pnpm dlx shadcn@latest add tabs` (Base UI tabs give roving focus + arrow keys). Style: list `self-start gap-1 rounded-lg bg-muted p-1`; trigger `h-10 px-4 rounded-tab text-body-sm font-medium text-muted-foreground`; active `bg-card text-primary-strong font-semibold shadow-tab`. Labels: "Type an answer" / "Upload audio". Switching tabs keeps both inputs.

Footer: `text-meta text-muted-foreground text-center`: "Your answers are reviewed by our HR team. Questions? Reply to your invitation email." Second line: "Demo: invitation emails are **mocked**. Links are printed by `make seed`." (AGENTS.md rule 5.)

Dropped from the design (user decision): the "← Previous question" link. The submit row puts the CTA on the right with nothing on the left.

### Local draft (`src/hooks/use-local-draft.ts`)
- Key `talotrace:draft:{token.slice(-8)}:{questionId}`. The token suffix scopes drafts per candidate on a shared device; no full token goes into storage.
- Read on mount, write on change (debounce ~300 ms). Every `localStorage` access goes in try/catch, so private mode still works.
- Clear after a successful text submit. The in-memory text is kept for "Back to this question".

### Time formatting
`new Intl.DateTimeFormat(undefined, { hour: "2-digit", minute: "2-digit" }).format(new Date(received_at))`, which matches the design's "received at 10:14".

## Related Code Files
- Create: `apps/web/src/app/i/[token]/page.tsx`
- Create: `apps/web/src/components/interview/{interview-screen,interview-header,interview-progress,answer-form,text-answer-field,audio-answer-dropzone,answer-receipt,interview-message-card}.tsx`
- Create: `apps/web/src/hooks/use-local-draft.ts`
- Create: `apps/web/src/lib/candidate-error-messages.ts`
- Create (shadcn CLI): `apps/web/src/components/ui/tabs.tsx`
- Modify: `apps/web/next.config.ts`: `headers()` for `/i/:path*` (plus the body-size limit if phase 4 needs it)

## Implementation Steps
1. `pnpm dlx shadcn@latest add tabs` in `apps/web`; restyle with tokens.
2. `use-local-draft.ts` + `candidate-error-messages.ts`.
3. Presentational components (header, progress, text field, dropzone, receipt, message card), each < 150 lines.
4. `answer-form.tsx` composes tabs + fields + error + submit.
5. `interview-screen.tsx` reducer + `getInterview` / `submit*` wiring; 401 → invalid screen; 409 → refetch; every inline message goes through `toCandidateMessage`.
6. `page.tsx` + `next.config.ts` headers.
7. `pnpm lint && pnpm typecheck`; run against a seeded link (`make seed` → copy a link from `apps/api/data/candidate-links.csv`).

## Success Criteria
- [x] Side-by-side with `Interview.dc.html` at 1440px: spacing, sizes, colors and radii match (except the dropped Previous link)
- [x] All states reachable: loading, invalid, load error, answering (text/audio), receipt, receipt-final, completed
- [x] Reload mid-interview resumes at `current_question`; typed draft restored
- [x] 360px width: no horizontal scroll; tabs and buttons wrap cleanly
- [x] Tab/arrow-key operable; dropzone opens the file picker with Enter/Space via the label/input
- [x] `rg '#[0-9a-fA-F]{3,6}' apps/web/src/components/interview` → no matches

## Risk Assessment
- `useParams` + `cacheComponents`: if Next requires Suspense for the client param read, wrap `<InterviewScreen />` in `<Suspense fallback={<loading skeleton/>}>` in `page.tsx`.
- Background refetch after submit can race with "Back to this question". Mitigation: the receipt screen keeps its own `question`, and the refetch only updates `view` (counts/progress).
- A token in the URL leaks via history and Referer. Referer is blocked by the header. History is accepted (personal link by design).
- Drag-drop of multiple files: take the first, ignore the rest.
