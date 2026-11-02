"use client";

// Two-panel sign-in from the Main.dc.html artboard: brand panel left, form
// panel right. Panels stack below ~1040px (both flex-basis 520px + wrap).

import { SignInBrandPanel } from "@/components/hr/sign-in/sign-in-brand-panel";
import { SignInForm } from "@/components/hr/sign-in/sign-in-form";

export function SignInScreen() {
  return (
    <div className="flex min-h-svh flex-wrap bg-card text-foreground">
      <SignInBrandPanel />
      <div className="flex flex-[1_1_520px] items-center justify-center bg-background px-6 py-14">
        <SignInForm />
      </div>
    </div>
  );
}
