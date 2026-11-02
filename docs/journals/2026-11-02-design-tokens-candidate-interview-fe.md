# 2026-11-02 — Design tokens + candidate interview FE

## What shipped

- `globals.css` rewritten as the single token source: light theme only, exact
  hex from the 4 design artboards, exposed via `@theme inline` (colors, fixed-px
  radii, shadows, text scale with line-height + tracking, container widths).
  Dark/chart/sidebar vars removed; Geist → Inter 400–700.
- shadcn primitives aligned to the design (button `xl`/`cta` sizes, badge
  status pills, textarea/input focus = `border-primary` + `outline-primary`,
  alert `success` variant, tabs restyled; `field-sizing-content` dropped so
  `rows` works).
- `/i/[token]` candidate interview page: client-rendered, Bearer token from the
  URL, `useReducer` state machine (loading → answer/receipt/completed, plus
  invalid / loadError), typed answers with localStorage drafts, audio upload
  with client-side ext/size checks + MIME inference from extension, receipt →
  next/back flows, completion states. `/i/*` sends `Referrer-Policy:
  no-referrer` + `X-Robots-Tag: noindex`.
- `experimental.proxyClientMaxBodySize: "30mb"` in `next.config.ts` — the
  rewrite proxy buffers bodies (default 10 MB) below the server's 25 MB audio
  cap; a real 20 MB upload 500'd through the rewrite before this.

## Decisions

- "Next question →" refetches the interview rather than trusting the
  post-submit background refresh — next/completed routing always follows the
  server.
- `<AnswerForm key={question.id}>` so a 409 resync to a different question
  remounts the form (no stale file/tab leaking across questions).
- Draft keys use an 8-char token suffix: per-candidate scoping on shared
  devices without putting the full token in storage.
- Friendly error copy keyed by the documented `detail` strings (doc → status →
  raw detail fallback); 401 always routes to the invalid-link screen.

## Verified

Browser smoke on seeded links: draft restore on reload, text + audio submit,
receipt + count, back-to-question replace, 20 MB upload through the rewrite,
completion receipt with no back button, completed screen on reload, rotated
token → invalid screen, 360 px layout. `make lint && make test` (59 tests) +
`pnpm build` green.
