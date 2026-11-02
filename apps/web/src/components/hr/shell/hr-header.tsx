"use client";

// HR header: brand link, nav, MOCK badge, session avatar + sign out.
// Header data (session email, needs-a-person count) is best-effort — a failed
// fetch must not break the page, so both render only when data arrives.

import Link from "next/link";
import { useRouter } from "next/navigation";
import { Suspense } from "react";

import { BrandMark } from "@/components/brand-mark";
import { HrNav } from "@/components/hr/shell/hr-nav";
import { Badge } from "@/components/ui/badge";
import { useHrResource } from "@/hooks/use-hr-resource";
import { getSession, signOut } from "@/lib/hr-api";

export function HrHeader() {
  const router = useRouter();
  const { data: session } = useHrResource(getSession, []);

  async function onSignOut() {
    try {
      await signOut(); // 204, idempotent — the cookie may already be gone
    } catch {
      // ignore: sign-out always lands on the sign-in page
    }
    router.replace("/hr/sign-in");
  }

  return (
    <header className="border-b bg-card">
      <div className="mx-auto flex max-w-app flex-wrap items-center gap-x-8 gap-y-4 px-6 py-3.5">
        <Link href="/hr" className="flex items-center gap-2.5">
          <BrandMark size="sm" />
          <span className="font-semibold text-body-lg">Interview Scoring</span>
        </Link>
        <Suspense>
          <HrNav />
        </Suspense>
        <div className="ml-auto flex items-center gap-3">
          <Badge variant="warning">Mock auth</Badge>
          <div
            className="flex size-8 items-center justify-center rounded-full bg-primary-subtle font-semibold text-meta text-primary-strong"
            title={session?.email}
          >
            HR
          </div>
          <button
            type="button"
            onClick={onSignOut}
            className="text-body-sm text-muted-foreground transition-colors hover:text-foreground"
          >
            Sign out
          </button>
        </div>
      </div>
    </header>
  );
}
