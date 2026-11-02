// Full-page states for the review screen: 404 card, fatal error (no data
// loaded yet), and the loading skeleton.

import Link from "next/link";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

export function ReviewNotFound() {
  return (
    <Card className="mx-auto mt-16 w-full max-w-md">
      <CardHeader>
        <CardTitle>This candidate doesn't exist</CardTitle>
        <CardDescription>
          They may have been removed.{" "}
          <Link
            href="/hr"
            className="text-primary-strong hover:text-primary-deep"
          >
            Back to open roles
          </Link>
        </CardDescription>
      </CardHeader>
    </Card>
  );
}

export function ReviewLoadError({
  error,
  onRetry,
}: {
  error: string;
  onRetry: () => void;
}) {
  return (
    <Alert variant="destructive" className="mt-8">
      <AlertTitle>Couldn't load the review</AlertTitle>
      <AlertDescription>
        {error}
        <Button
          variant="secondary"
          size="sm"
          className="ml-3"
          onClick={onRetry}
        >
          Retry
        </Button>
      </AlertDescription>
    </Alert>
  );
}

export function ReviewSkeleton() {
  return (
    <div className="flex flex-col gap-5" aria-busy="true">
      <div className="h-24 animate-pulse rounded-2xl bg-muted" />
      {["q1", "q2", "q3"].map((k) => (
        <div key={k} className="h-64 animate-pulse rounded-2xl bg-muted" />
      ))}
    </div>
  );
}
