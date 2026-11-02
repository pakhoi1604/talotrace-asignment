"use client";

// MOCK sign-in form (labeled). The only working account is HR_EMAIL /
// HR_PASSWORD from apps/api/.env; the API answers 401 for anything else.
// On success: router.replace(safeNext(next)) — `next` is /hr/* only.

import { useRouter, useSearchParams } from "next/navigation";
import { useRef, useState } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { signIn } from "@/lib/hr-api";
import { safeNext } from "@/lib/hr-auth-redirect";
import { toHrMessage } from "@/lib/hr-error-messages";

export function SignInForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const passwordRef = useRef<HTMLInputElement>(null);
  const [error, setError] = useState<string>();
  const [pending, setPending] = useState(false);

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const email = (form.elements.namedItem("email") as HTMLInputElement).value;
    const passwordInput = form.elements.namedItem(
      "password",
    ) as HTMLInputElement;
    setPending(true);
    setError(undefined);
    try {
      await signIn(email.trim(), passwordInput.value);
      router.replace(safeNext(searchParams.get("next")));
    } catch (err) {
      setError(toHrMessage(err));
      passwordInput.value = "";
      passwordRef.current?.focus();
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="flex w-full max-w-auth flex-col gap-7">
      <div className="flex flex-col gap-2.5">
        <Badge
          variant="warning"
          className="self-start border-warning-border-strong"
        >
          Mocked sign-in — demo only
        </Badge>
        <h2 className="font-bold text-display-sm">Sign in to HR</h2>
        <p className="text-body text-muted-foreground">
          Review candidates and their suggested scores.
        </p>
      </div>

      <form
        onSubmit={onSubmit}
        className="flex flex-col gap-4.5 rounded-2xl border bg-card p-7 shadow-card-raised"
      >
        {error && (
          <Alert variant="destructive">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="email" className="text-body-sm text-foreground-soft">
            Work email
          </Label>
          <Input
            id="email"
            name="email"
            type="email"
            autoComplete="username"
            required
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <div className="flex items-baseline justify-between">
            <Label
              htmlFor="password"
              className="text-body-sm text-foreground-soft"
            >
              Password
            </Label>
            <span className="text-meta text-muted-foreground">
              Demo account is in{" "}
              <code className="font-mono text-caption">apps/api/.env</code>
            </span>
          </div>
          <Input
            ref={passwordRef}
            id="password"
            name="password"
            type="password"
            autoComplete="current-password"
            required
          />
        </div>
        <Button
          type="submit"
          size="xl"
          className="mt-1 w-full"
          disabled={pending}
        >
          {pending ? "Signing in…" : "Sign in"}
        </Button>
      </form>

      <p className="text-center text-body-sm text-muted-foreground leading-[1.6]">
        Are you a candidate? Open the personal link from your invitation email —
        no account needed.
      </p>
    </div>
  );
}
