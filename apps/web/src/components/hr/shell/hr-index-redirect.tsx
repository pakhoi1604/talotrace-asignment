"use client";

// /hr → first role (roles are title-sorted by the API). No roles → the
// make-seed empty state; API error → alert + Retry.

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { useHrResource } from "@/hooks/use-hr-resource";
import { listRoles } from "@/lib/hr-api";

export function HrIndexRedirect() {
  const router = useRouter();
  const { data, error, loading, reload } = useHrResource(listRoles, []);

  useEffect(() => {
    const first = data?.roles[0];
    if (first) router.replace(`/hr/roles/${first.id}`);
  }, [data, router]);

  if (data && data.roles.length === 0) {
    return (
      <Card className="mx-auto mt-16 w-full max-w-md">
        <CardHeader>
          <CardTitle>No roles yet</CardTitle>
          <CardDescription>
            Run <code className="font-mono">make seed</code> to load the data
            pack.
          </CardDescription>
        </CardHeader>
      </Card>
    );
  }

  if (error) {
    return (
      <Alert variant="destructive" className="mx-auto mt-16 max-w-md">
        <AlertTitle>Couldn't load roles</AlertTitle>
        <AlertDescription>
          {error}
          <Button
            variant="secondary"
            size="sm"
            className="ml-3"
            onClick={() => void reload()}
          >
            Retry
          </Button>
        </AlertDescription>
      </Alert>
    );
  }

  return (
    <p className="mt-16 text-center text-body text-muted-foreground">
      {loading ? "Loading…" : "Redirecting to the first role…"}
    </p>
  );
}
