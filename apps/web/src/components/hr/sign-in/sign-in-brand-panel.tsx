"use client";

// Left brand panel of the sign-in artboard: brand mark + hero copy + three
// feature rows + footer. Icon bubbles are primary-foreground at 16% opacity
// (the artboard's translucent-white bubble) — token + opacity modifier, no hex.

import { Clock, Pencil, SquareCheck } from "lucide-react";

import { BrandMark } from "@/components/brand-mark";

const FEATURES = [
  { icon: SquareCheck, text: "Suggested scores with a written reason" },
  { icon: Clock, text: "Every scoring job visible — queued, scored, failed" },
  { icon: Pencil, text: "Overrides always keep HR's reason" },
] as const;

export function SignInBrandPanel() {
  return (
    <div className="flex min-h-[420px] flex-[1_1_520px] flex-col justify-between gap-12 bg-primary-strong px-16 py-14 text-primary-foreground">
      <div className="flex items-center gap-3">
        <BrandMark size="lg" tone="inverse" />
        <span className="font-semibold text-title tracking-[-0.01em]">
          Interview Scoring
        </span>
      </div>

      <div className="flex max-w-[480px] flex-col gap-6">
        <h1 className="font-bold text-display">
          The system suggests.
          <br />
          You decide.
        </h1>
        <p className="text-lead text-primary-subtle">
          Every answer gets a suggested score from 1 to 4, with the reason
          behind it. HR reviews, overrides when needed, and makes the call.
        </p>
        <ul className="mt-2 flex flex-col gap-3.5">
          {FEATURES.map(({ icon: Icon, text }) => (
            <li key={text} className="flex items-center gap-3 text-body">
              <span className="flex size-7 items-center justify-center rounded-sm bg-primary-foreground/16">
                <Icon className="size-4" aria-hidden />
              </span>
              <span>{text}</span>
            </li>
          ))}
        </ul>
      </div>

      <p className="text-meta text-primary-border">
        Internal tool · HR team only
      </p>
    </div>
  );
}
