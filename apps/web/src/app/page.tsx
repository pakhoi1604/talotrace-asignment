import { Suspense } from "react";

import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { apiFetchServer } from "@/lib/api-client";
import type { HealthResponse } from "@/lib/api-types";

async function HealthStatus() {
  let health: HealthResponse | null = null;
  try {
    health = await apiFetchServer<HealthResponse>("/api/health");
  } catch {
    health = null;
  }

  if (!health) {
    return (
      <Badge variant="destructive">
        API unreachable — start the backend with `make dev`
      </Badge>
    );
  }

  return (
    <div className="flex gap-2">
      <Badge variant={health.status === "ok" ? "default" : "destructive"}>
        api: {health.status}
      </Badge>
      <Badge variant={health.db === "ok" ? "default" : "destructive"}>
        db: {health.db}
      </Badge>
    </div>
  );
}

export default function Home() {
  return (
    <main className="flex flex-1 items-center justify-center p-8">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>TaloTrace</CardTitle>
          <CardDescription>
            HR interview scoring — the system suggests, HR decides.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Suspense fallback={<Badge variant="outline">Checking API…</Badge>}>
            <HealthStatus />
          </Suspense>
        </CardContent>
      </Card>
    </main>
  );
}
