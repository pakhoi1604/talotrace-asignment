"use client";

// /hr/jobs?status= client root: filter from the URL, data, inline retry.
// "Queued" filters to queued only — running jobs show under All (the API
// filters one status at a time; noted in the footnote). An unknown status
// param is treated as All so it never reaches the API as a 422.

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";

import {
  type JobFilter,
  JobsFilterChips,
} from "@/components/hr/jobs/jobs-filter-chips";
import { JobsPageHeading } from "@/components/hr/jobs/jobs-page-heading";
import { JobsTable } from "@/components/hr/jobs/jobs-table";
import { RefreshButton } from "@/components/hr/refresh-button";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { useHrResource } from "@/hooks/use-hr-resource";
import { ApiRequestError } from "@/lib/api-client";
import type { JobListItem, JobStatus } from "@/lib/api-types";
import { listJobs, retryJob } from "@/lib/hr-api";
import { useHrUnauthorizedRedirect } from "@/lib/hr-auth-redirect";
import { toHrMessage } from "@/lib/hr-error-messages";

const VALID_FILTERS = new Set<JobFilter>([
  "queued",
  "scored",
  "failed",
  "needs_person",
  "superseded",
]);

function readFilter(raw: string | null): JobFilter {
  return VALID_FILTERS.has(raw as JobFilter) ? (raw as JobFilter) : "all";
}

const EMPTY: Record<JobFilter, string> = {
  all: "No jobs yet.",
  queued: "No queued jobs.",
  scored: "No scored jobs.",
  failed: "No failed jobs.",
  needs_person: "Nothing needs a person right now.",
  superseded: "No replaced jobs.",
};

export function JobsScreen() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const onUnauthorized = useHrUnauthorizedRedirect();
  const filter = readFilter(searchParams.get("status"));
  const jobs = useHrResource(
    () => listJobs(filter === "all" ? undefined : (filter as JobStatus)),
    [filter],
  );
  const [retrying, setRetrying] = useState<number | null>(null);
  const [actionError, setActionError] = useState<string>();

  function setFilter(next: JobFilter) {
    setActionError(undefined);
    router.replace(next === "all" ? pathname : `${pathname}?status=${next}`);
  }

  async function onRetry(job: JobListItem) {
    setRetrying(job.id);
    setActionError(undefined);
    try {
      await retryJob(job.id);
      await jobs.reload();
    } catch (err) {
      if (onUnauthorized(err)) return;
      setActionError(toHrMessage(err));
      if (err instanceof ApiRequestError && err.status === 409)
        await jobs.reload();
    } finally {
      setRetrying(null);
    }
  }

  return (
    <div className="flex flex-col gap-5">
      <JobsPageHeading
        needsPerson={filter === "needs_person"}
        refresh={
          <RefreshButton
            refreshing={jobs.refreshing}
            loadedAt={jobs.loadedAt}
            onRefresh={() => void jobs.reload()}
          />
        }
      />
      <div className="flex flex-wrap items-center gap-3">
        <JobsFilterChips
          counts={jobs.data?.counts}
          value={filter}
          onChange={setFilter}
        />
      </div>
      {actionError && (
        <Alert variant="destructive">
          <AlertDescription>{actionError}</AlertDescription>
        </Alert>
      )}
      {jobs.error && jobs.data && (
        <Alert variant="destructive">
          <AlertDescription>{jobs.error}</AlertDescription>
        </Alert>
      )}
      {jobs.error && !jobs.data ? (
        <Alert variant="destructive">
          <AlertTitle>Couldn't load jobs</AlertTitle>
          <AlertDescription>
            {jobs.error}
            <Button
              variant="secondary"
              size="sm"
              className="ml-3"
              onClick={() => void jobs.reload()}
            >
              Retry
            </Button>
          </AlertDescription>
        </Alert>
      ) : jobs.loading || !jobs.data ? (
        <div
          className="h-80 animate-pulse rounded-2xl bg-muted"
          aria-busy="true"
        />
      ) : (
        <JobsTable
          jobs={jobs.data.jobs}
          emptyLabel={EMPTY[filter]}
          retrying={retrying}
          onRetry={onRetry}
        />
      )}
      <p className="m-0 text-meta text-muted-foreground">
        Jobs being scored right now show under All. Scores live on the candidate
        review page.
      </p>
    </div>
  );
}
