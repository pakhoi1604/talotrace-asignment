"use client";

// Auth redirect helpers for the HR area. The proxy redirects early when the
// `hr_session` cookie is absent (presence only — the API decides validity);
// this hook covers expired/revoked sessions surfaced as 401s by HR calls.

import { usePathname, useRouter } from "next/navigation";
import { useCallback } from "react";

import { ApiRequestError } from "@/lib/api-client";

/** Only paths under /hr/ are allowed as sign-in `next` targets (no open redirect). */
export function safeNext(raw: string | null): string {
  if (raw?.startsWith("/hr/") && !raw.startsWith("//")) return raw;
  return "/hr";
}

/**
 * Returns a handler: on an API 401 it redirects to sign-in with `next` set to
 * the current URL and returns true; any other error returns false.
 */
export function useHrUnauthorizedRedirect() {
  const router = useRouter();
  const pathname = usePathname();
  return useCallback(
    (err: unknown) => {
      if (err instanceof ApiRequestError && err.status === 401) {
        const here = pathname + window.location.search;
        router.replace(`/hr/sign-in?next=${encodeURIComponent(here)}`);
        return true;
      }
      return false;
    },
    [router, pathname],
  );
}
