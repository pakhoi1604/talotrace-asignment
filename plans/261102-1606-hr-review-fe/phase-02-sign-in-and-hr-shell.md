---
phase: 2
title: "Sign-in + HR shell"
status: completed
priority: P1
dependencies: [1]
---

# Phase 2: Sign-in + HR shell

## Overview
`/hr/sign-in` faithful to `Main.dc.html` (with the reconciled copy), the authenticated HR layout with the header/nav from the dashboard and review artboards, sign-out, and `/hr` → first role.

## Requirements
- Functional: sign in with the `.env` account; redirect to `safeNext(next)`; show friendly errors; header shows MOCK badge, HR avatar, email (title attr), nav with active state and needs-a-person count, sign out.
- Non-functional: sign-in works on keyboard only; labels tied to inputs; submit disabled while pending; responsive (two panels stack under ~1040px); `robots: noindex` on all HR routes; tokens only.

## Architecture

### Route layout (App Router)
```
src/app/hr/layout.tsx                    metadata { title template "%s · HR", robots noindex }; no chrome
src/app/hr/sign-in/page.tsx              <Suspense><SignInScreen /></Suspense>   (useSearchParams)
src/app/hr/(app)/layout.tsx              <HrShell>{children}</HrShell>  (client header + main container)
src/app/hr/(app)/page.tsx                <HrIndexRedirect />  → /hr/roles/{first id}
src/app/hr/(app)/roles/[roleId]/page.tsx        phase 3
src/app/hr/(app)/candidates/[candidateId]/page.tsx  phase 4
src/app/hr/(app)/jobs/page.tsx                   phase 5
```

### Sign-in (`src/components/hr/sign-in/`)
| File | Responsibility | Design ref |
|---|---|---|
| `sign-in-screen.tsx` | two-panel flex wrap (`flex-[1_1_520px]`), left brand panel + right form panel `bg-background` | root |
| `sign-in-brand-panel.tsx` | `bg-primary-strong text-primary-foreground px-16 py-14`; `<BrandMark size="lg" tone="inverse" />` (phase 1); "Interview Scoring"; h1 `text-display` "The system suggests.<br/>You decide."; lead `text-lead text-primary-subtle`; 3 feature rows (icon bubble `size-7 rounded-sm bg-white/16`, lucide `SquareCheck`, `Clock`, `Pencil`); footer `text-meta text-primary-border` "Internal tool · HR team only" | left panel |
| `sign-in-form.tsx` | badge `variant="warning"` + `border border-warning-border-strong` (design `#FCD34D` border) "Mocked sign-in — demo only"; h2 `text-display-sm` "Sign in to HR"; sub "Review candidates and their suggested scores."; card `rounded-2xl border bg-card p-7 shadow-card-raised`; `Label` "Work email" + `Input type=email autoComplete=username required`; "Password" + hint "Demo account is in apps/api/.env" + `Input type=password autoComplete=current-password required`; `Button` full width `h-12` "Sign in" / "Signing in…"; inline `Alert variant="destructive"` from `toHrMessage`; footer "Are you a candidate? Open the personal link from your invitation email — no account needed." (`text-body-sm text-muted-foreground text-center`) | right panel |

Flow: submit → `signIn()` → `router.replace(safeNext(searchParams.get("next")))`. 401 / 503 / network → inline alert, password cleared, focus back to the password field. If already signed in (cookie valid), visiting `/hr/sign-in` is fine: no auto-redirect (keep simple).

Note: the white rgba icon bubble (`rgba(255,255,255,0.16)`) uses `bg-primary-foreground/16`, not a raw value.

### Shell (`src/components/hr/shell/`)
| File | Responsibility | Design ref |
|---|---|---|
| `hr-shell.tsx` | client; `<HrHeader/>` + `<main className="mx-auto max-w-app px-6 pt-8 pb-16 flex flex-col gap-6">` | page frame |
| `hr-header.tsx` | `bg-card border-b`; inner `max-w-app px-6 py-3.5 flex flex-wrap gap-x-8 gap-y-4`; brand (`<BrandMark size="sm" />`, "Interview Scoring" `text-body-lg font-semibold`) linking to `/hr`; `<HrNav/>`; right: `Badge variant="warning"` "Mock auth", avatar `size-8 rounded-full bg-primary-subtle text-primary-strong` "HR" with `title={session.email}`, "Sign out" button (link style, `text-muted-foreground`) | `<header>` |
| `hr-nav.tsx` | 3 links: Candidates (`/hr` and `/hr/roles/*`, `/hr/candidates/*` active), Needs a person (`/hr/jobs?status=needs_person`) + warning count pill, Scoring jobs (`/hr/jobs` without that status). Inactive = `text-body-sm font-medium text-foreground-body`; active = `bg-primary-soft text-primary-strong font-semibold rounded-sm px-3 py-2`; `aria-current="page"` | nav |

Header data: `useHrResource(getSession)` for the email and `useHrResource(listRoles)` for the needs-a-person count (sum of `job_counts.needs_person`). Count pill hidden at 0. Header data failing must not break the page (render without email/count).

Sign out: `await signOut()` (ignore errors, the cookie may already be gone) → `router.replace("/hr/sign-in")`.

### `/hr` index (`hr-index-redirect.tsx`)
`listRoles()` → `router.replace(/hr/roles/{roles[0].id})` (roles are title-sorted by the API). Empty → empty state card "No roles yet. Run `make seed` to load the data pack." Error → `Alert` + Retry.

## Related Code Files
- Create: `apps/web/src/app/hr/layout.tsx`, `hr/sign-in/page.tsx`, `hr/(app)/layout.tsx`, `hr/(app)/page.tsx`
- Create: `apps/web/src/components/hr/sign-in/{sign-in-screen,sign-in-brand-panel,sign-in-form}.tsx`
- Create: `apps/web/src/components/hr/shell/{hr-shell,hr-header,hr-nav,hr-index-redirect}.tsx`

## Implementation Steps
<!-- Updated: user request 2026-11-02 - inspect design + map colors to tokens -->
0. **Inspect + map colors first.** Open `Main.dc.html` (sign-in) and the `<header>` of `HRDashboard.dc.html`, list every color in the part you're building, and map each one to its token with the [color map](phase-01-gate-and-hr-api-client-plumbing.md#design-color--token-map). Code uses token utilities only: no hex, `rgb(a)`, `hsl`, `bg-[#…]` or inline color styles. Pick by role where one value maps to several tokens. Expected tokens: background, primary-strong, primary-foreground (+ `/16`), primary-subtle, primary-border, card, foreground, foreground-soft, muted-foreground, input, primary, ring, warning-subtle, warning-ink, warning-border-strong, border, primary-soft, foreground-body, shadow-card-raised.
1. Route files + metadata.
2. Sign-in components; wire `signIn` + `safeNext`.
3. Shell, nav active logic (`usePathname` + `useSearchParams` inside Suspense).
4. Index redirect + empty state.
5. `pnpm lint && pnpm typecheck && pnpm build`.
6. Browser: wrong password → alert; right → lands on first role; sign out → sign-in; back button after sign-out → redirected (proxy or 401).

## Success Criteria
- [ ] Every color in this phase's UI traces to a token in the color map; `grep` finds no hex/rgb/hsl/arbitrary color in the files created here
- [ ] Sign-in matches `Main.dc.html` layout/spacing with the reconciled copy; MOCK badge visible
- [ ] `?next=https://evil.test` → lands on `/hr` (open-redirect guard)
- [ ] Header shows "Mock auth", nav active state correct on all HR routes, sign out works (204 handled)
- [ ] `/hr` with no roles shows the `make seed` empty state
- [ ] Build green (no missing-Suspense errors from `useSearchParams` under `cacheComponents`)

## Risk Assessment
- Route group `(app)` + root `hr/layout.tsx`: keep the sign-in page outside the shell. Verify the sign-in page renders without header.
- `bg-primary-foreground/16` needs Tailwind v4 opacity modifiers on CSS-var colors (supported). If the modifier doesn't resolve, report it. Don't fall back to `bg-white/*`, a hex or an arbitrary value (tokens only).
