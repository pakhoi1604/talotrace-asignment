"use client";

// /hr/roles/[roleId] client root: data, sort state, load/error/404 states.

import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";

import { RefreshButton } from "@/components/hr/refresh-button";
import { CandidateTable } from "@/components/hr/role/candidate-table";
import { RoleFootnote } from "@/components/hr/role/role-footnote";
import { RoleHeader } from "@/components/hr/role/role-header";
import { RoleStatCards } from "@/components/hr/role/role-stat-cards";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { useHrResource } from "@/hooks/use-hr-resource";
import { getRoleCandidates, listRoles } from "@/lib/hr-api";
import type { CandidateSort } from "@/lib/hr-role-stats";
import { roleStats, sortCandidates } from "@/lib/hr-role-stats";

export function RoleCandidatesScreen() {
  const { roleId } = useParams<{ roleId: string }>();
  const roles = useHrResource(listRoles, []);
  const rc = useHrResource(() => getRoleCandidates(roleId), [roleId]);
  const [sort, setSort] = useState<CandidateSort>("name");

  if (rc.status === 404 && !rc.data) {
    return (
      <Card className="mx-auto mt-16 w-full max-w-md">
        <CardHeader>
          <CardTitle>This role doesn't exist</CardTitle>
          <CardDescription>
            It may have been removed.{" "}
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

  // A failed initial load gets the full-page error; a failed Refresh only
  // banners — the old data stays visible (manual-refresh contract).
  if (rc.error && !rc.data) {
    return (
      <Alert variant="destructive" className="mt-8">
        <AlertTitle>Couldn't load candidates</AlertTitle>
        <AlertDescription>
          {rc.error}
          <Button
            variant="secondary"
            size="sm"
            className="ml-3"
            onClick={() => void rc.reload()}
          >
            Retry
          </Button>
        </AlertDescription>
      </Alert>
    );
  }

  if (rc.loading || !rc.data) {
    return (
      <div className="flex flex-col gap-6" aria-busy="true">
        <div className="h-16 animate-pulse rounded-md bg-muted" />
        <div className="grid grid-cols-[repeat(auto-fit,minmax(170px,1fr))] gap-4">
          {["c", "a", "s", "q", "f", "n"].map((k) => (
            <div key={k} className="h-24 animate-pulse rounded-xl bg-muted" />
          ))}
        </div>
        <div className="h-80 animate-pulse rounded-2xl bg-muted" />
      </div>
    );
  }

  const stats = roleStats(rc.data);
  const rows = sortCandidates(rc.data.candidates, sort);

  return (
    <>
      {rc.error && (
        <Alert variant="destructive">
          <AlertDescription>{rc.error}</AlertDescription>
        </Alert>
      )}
      <RoleHeader
        role={rc.data.role}
        roles={roles.data?.roles}
        openRoles={roles.data?.roles.length}
        refresh={
          <RefreshButton
            refreshing={rc.refreshing}
            loadedAt={rc.loadedAt}
            onRefresh={() => void rc.reload()}
          />
        }
      />
      <RoleStatCards stats={stats} />
      <CandidateTable
        rows={rows}
        totalQuestions={rc.data.total_questions}
        sort={sort}
        onSortChange={setSort}
      />
      <RoleFootnote />
    </>
  );
}
