---
phase: 3
title: "Frontend skeleton (Next.js + Tailwind + Biome + shadcn)"
status: completed
priority: P1
dependencies: [1]
---

# Phase 3: Frontend skeleton

## Overview
A Next.js App Router app with Tailwind v4, Biome as the only linter/formatter, shadcn initialised with only the components the required features need, and a typed API client that proxies to FastAPI.

## Requirements
- Functional: home page renders API health from `/api/health` (proves the proxy + DB wiring end to end)
- Non-functional: `biome check` and `tsc --noEmit` clean. No ESLint/Prettier

## Architecture
- `next.config.ts` rewrites: `/api/:path*` → `${API_URL ?? "http://localhost:8000"}/api/:path*`. The browser stays same-origin, which means no CORS and lets the HR session cookie work later.
- `src/lib/api-client.ts`: small `apiFetch<T>(path, init)` wrapper. It throws on non-2xx with the `detail` message.
- `src/lib/api-types.ts`: TS types mirrored from `docs/api-doc.md` (only `HealthResponse` for now).
- Route groups `(candidate)` and `(hr)` are **not** created yet. They come with their feature plans (YAGNI).

## shadcn components (required features only)
| Component | Used by (required) |
|---|---|
| button | everywhere |
| card | candidate question view, HR answer panel |
| textarea | candidate typed answer, HR override reason |
| input, label | audio file input, mock sign-in |
| alert | candidate "answer received" confirmation |
| table | HR candidate/answer list |
| badge | job status (queued / scored / failed / needs a person), score |
| dialog | HR override score + required reason |
| select | HR role picker, override score 1–4 |

Not added: toast/sonner, form, tabs, dropdown, skeleton, etc. Add them later with `pnpm dlx shadcn@latest add <name>` only when a feature needs them.

## Related Code Files
- Create: `apps/web/**` (scaffold), `biome.json`, `components.json`, `src/lib/api-client.ts`, `src/lib/api-types.ts`, `.env.example`
- Modify: `src/app/page.tsx` (health view), `next.config.ts` (rewrites), `package.json` scripts

## Implementation Steps
1. `cd apps && pnpm create next-app@latest web --ts --tailwind --app --src-dir --import-alias "@/*" --no-eslint --use-pnpm --turbopack` (if the prompt asks about the React Compiler, say no).
2. `cd web && pnpm add -D @biomejs/biome && pnpm biome init`. Configure `biome.json`: formatter (2 spaces, double quotes), linter recommended, enable `useSortedClasses` (nursery/Tailwind) if available, ignore `.next`, `node_modules`, `src/components/ui` (vendored shadcn code. Format only, don't lint).
3. `package.json` scripts: `"lint": "biome check ."`, `"format": "biome check --write ."`, `"typecheck": "tsc --noEmit"`. Remove any eslint remnants.
4. `pnpm dlx shadcn@latest init` (base color neutral, CSS variables), then `pnpm dlx shadcn@latest add button card textarea input label alert table badge dialog select`.
5. Add rewrites to `next.config.ts`. Add `.env.example` with `API_URL=http://localhost:8000`.
6. Write `api-client.ts` and `api-types.ts`. Replace the boilerplate `page.tsx` with a server component that fetches `${API_URL}/api/health` (server side, absolute URL) and renders a `Card` + `Badge` showing api/db status, or an error state if the API is down.
7. Strip the create-next-app demo assets (`public/*.svg`, demo CSS) and keep `globals.css` limited to Tailwind + shadcn tokens.
8. `pnpm lint && pnpm typecheck && pnpm build`.

## Success Criteria
- [x] `pnpm lint`, `pnpm typecheck`, `pnpm build` pass
- [x] Only the 10 listed components exist in `src/components/ui/`
- [x] With the api running, `/` shows `api: ok, db: ok`. With it stopped, a clear "API unreachable" state shows

## Risk Assessment
- create-next-app flags drift between versions. Check against `pnpm create next-app@latest --help` before running.
- Biome vs Tailwind v4 class sorting: rule names change across Biome versions. If the rule is unavailable, skip it (not essential).
- Server components can't use relative `/api` URLs, so server-side fetches use `API_URL` directly while client fetches use the rewrite. Document this in `api-client.ts`.
