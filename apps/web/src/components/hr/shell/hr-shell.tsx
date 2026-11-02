"use client";

// Authenticated HR frame: header + centered 1280px content column.
// Sign-in lives outside this shell (route group `(app)`).

import { Suspense } from "react";

import { BrandMark } from "@/components/brand-mark";
import { HrHeader } from "@/components/hr/shell/hr-header";

// Static fallback while the header's client hooks stream in under cacheComponents.
function HeaderFallback() {
  return (
    <header className="border-b bg-card">
      <div className="mx-auto flex max-w-app items-center gap-2.5 px-6 py-3.5">
        <BrandMark size="sm" />
        <span className="font-semibold text-body-lg">Interview Scoring</span>
      </div>
    </header>
  );
}

export function HrShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-svh flex-col bg-background">
      <Suspense fallback={<HeaderFallback />}>
        <HrHeader />
      </Suspense>
      <main className="mx-auto flex w-full max-w-app flex-col gap-6 px-6 pt-8 pb-16">
        {children}
      </main>
    </div>
  );
}
