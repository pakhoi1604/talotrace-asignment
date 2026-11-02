---
phase: 2
title: "Candidate API client + types"
status: done
priority: P1
dependencies: [1]
---

# Phase 2: Candidate API client + types

## Overview
Add a typed client for the three candidate endpoints, learned **only** from `docs/api-doc.md`. This phase is gated by the cross-plan blocker.

<!-- Updated: Validation Session 1 - api-doc gate satisfied; contract replaced with verified one; MIME inference added -->
## Gate (satisfied 2026-11-02, re-check before coding)
`docs/api-doc.md` documents all 3 candidate endpoints, and `apps/web/src/lib/api-types.ts` (`InterviewView`, `CurrentQuestion`, `AnsweredItem`, `AnswerReceipt`, `TextAnswerRequest`, `AnswerKind`) mirrors it. Before coding, re-open the doc. If it changed, update the types to match the doc. If the candidate section is gone, stop with `Status: BLOCKED`. Never read `apps/api` to infer shapes.

## Verified contract (summary of `docs/api-doc.md`; the doc wins on any later change)
- Auth: `Authorization: Bearer <token>`. Every auth failure → 401 `invalid or missing candidate token`.
- `GET /api/candidate/interview` → `InterviewView`. `completed: true` ⇒ `current_question: null`. `answered` is ordered by position.
- `PUT /api/candidate/answers/{question_id}` JSON `{ text }` → **201 created or replaced** / 200 identical replay → `AnswerReceipt`.
- `PUT /api/candidate/answers/{question_id}/audio` multipart `file` → same receipt and status rules.
- Error `detail` strings (input for phase 3's friendly-copy map): 404 `question not found` · 409 `answer the current question first` / `interview is closed` / `another submission for this question is in progress, please retry` · 413 `audio file too large (max 25 MB)` · 415 `unsupported audio type` · 422 `text: must not be blank` / `text: must be at most 10000 characters` / `file: Field required` / `audio file is empty` / `body: Field required`.
- Audio accepted: ext `.m4a .mp3 .wav .webm .ogg .mp4` **and** content-type `audio/*`, `video/mp4` or `video/webm`.

## Requirements
- Functional: `getInterview`, `submitTextAnswer`, `submitAudioAnswer`, all browser-side (same-origin `/api/*` via the existing rewrite); typed errors keep the HTTP status for UI mapping.
- Non-functional: the token is sent only in the `Authorization` header, never in an API path or query, and never logged; `cache: "no-store"`; no `Content-Type` header on multipart (the browser sets the boundary).

## Architecture
`src/lib/api-client.ts`: `request()` already takes `RequestInit`, so headers pass through and nothing changes there. Reuse `ApiRequestError(status, detail)`.

`src/lib/candidate-api.ts` (new):
```ts
const auth = (token: string) => ({ Authorization: `Bearer ${token}` });

export const getInterview = (token: string) =>
  apiFetch<InterviewView>("/api/candidate/interview", { headers: auth(token), cache: "no-store" });

export const submitTextAnswer = (token: string, questionId: string, text: string) =>
  apiFetch<AnswerReceipt>(`/api/candidate/answers/${encodeURIComponent(questionId)}`, {
    method: "PUT",
    headers: { ...auth(token), "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });

// Some OS/browser combos label .m4a etc. as "" or application/octet-stream → server 415.
// Re-wrap with a type inferred from the extension (bytes unchanged, so replays still match).
const AUDIO_MIME_BY_EXT: Record<string, string> = {
  ".m4a": "audio/mp4", ".mp3": "audio/mpeg", ".wav": "audio/wav",
  ".webm": "audio/webm", ".ogg": "audio/ogg", ".mp4": "video/mp4",
};
export function withAudioMime(file: File): File {
  if (/^(audio\/|video\/(mp4|webm)$)/.test(file.type)) return file;
  const ext = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
  const type = AUDIO_MIME_BY_EXT[ext];
  return type ? new File([file], file.name, { type }) : file;
}

export function submitAudioAnswer(token: string, questionId: string, file: File) {
  const body = new FormData();
  body.append("file", withAudioMime(file));
  return apiFetch<AnswerReceipt>(`/api/candidate/answers/${encodeURIComponent(questionId)}/audio`, {
    method: "PUT", headers: auth(token), body,
  });
}
```
Also export the client-side guard constants, copied from the api-doc limits and commented `// mirrors docs/api-doc.md`: `MAX_TEXT_CHARS = 10_000`, `MAX_AUDIO_BYTES = 25 * 1024 * 1024`, `AUDIO_EXTENSIONS = [".m4a", ".mp3", ".wav", ".webm", ".ogg", ".mp4"]`. They exist for UX only; the server stays the authority.

## Related Code Files
- Create: `apps/web/src/lib/candidate-api.ts`
- Verify/modify: `apps/web/src/lib/api-types.ts`: `InterviewView`, `CurrentQuestion`, `AnsweredItem`, `AnswerReceipt` must match the doc
- No change: `apps/web/src/lib/api-client.ts`, `next.config.ts` rewrite

## Implementation Steps
1. Re-check the gate above.
2. Reconcile `api-types.ts` with the doc (expected: no change).
3. Write `candidate-api.ts`, including `withAudioMime`.
4. `pnpm lint && pnpm typecheck`.
5. Quick smoke in the browser console on any page, with a seeded token: `getInterview(token)` returns the view, a bad token throws `ApiRequestError` with status 401, and `withAudioMime(new File(["x"], "a.m4a", { type: "" })).type === "audio/mp4"`.

## Success Criteria
- [x] Gate re-checked
- [x] Types mirror `api-doc.md` field by field
- [x] Three functions typed; multipart sends no manual Content-Type
- [x] `withAudioMime` fixes empty/octet-stream types for the 6 allowed extensions and leaves valid types untouched
- [x] lint + typecheck green

## Risk Assessment
- Contract drift between the backend plan's draft and the final api-doc: mitigated by the gate + "doc wins" rule.
- The Next rewrite proxies multipart bodies up to Next's proxy limits. If 25 MB uploads fail through the rewrite (body size limit), set `experimental.proxyClientMaxBodySize` (or the Next 16 equivalent) in `next.config.ts` to ≥ 26 MB. Check this during phase 4 with a ~20 MB file.
