"use client";

// Jobs table: status chip, candidate link, role, question + answer kind,
// detail (needs-a-person reason / last error / attempt), updated, action.
// No score columns — JobListItem carries none; scores live on the review page.

import { cn } from "cn";
import { AlignLeft, Mic, RotateCw } from "lucide-react";
import Link from "next/link";
import { JobStatusChip } from "@/components/hr/job-status-chip";
import { Button, buttonVariants } from "@/components/ui/button";
import type { JobListItem } from "@/lib/api-types";
import { formatRelative } from "@/lib/hr-format";

const TH =
  "px-4 py-3 text-left text-caption font-semibold uppercase tracking-[0.04em] text-muted-foreground";
const TD = "border-b border-border-subtle px-4 py-4 align-middle text-body-sm";

function detail(job: JobListItem): string {
  if (job.status === "needs_person") return job.needs_person_reason ?? "—";
  if (job.status === "failed") return job.last_error ?? "—";
  if (job.status === "queued" || job.status === "running")
    return `attempt ${job.attempts}`;
  return "—";
}

interface JobsTableProps {
  jobs: JobListItem[];
  emptyLabel: string;
  retrying: number | null;
  onRetry: (job: JobListItem) => void;
}

export function JobsTable({
  jobs,
  emptyLabel,
  retrying,
  onRetry,
}: JobsTableProps) {
  return (
    <section className="overflow-hidden rounded-2xl border bg-card">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[880px] border-collapse">
          <thead className="bg-surface-subtle">
            <tr>
              <th scope="col" className={TH}>
                Status
              </th>
              <th scope="col" className={TH}>
                Candidate
              </th>
              <th scope="col" className={TH}>
                Role
              </th>
              <th scope="col" className={TH}>
                Question
              </th>
              <th scope="col" className={TH}>
                Detail
              </th>
              <th scope="col" className={TH}>
                Updated
              </th>
              <th scope="col" className={cn(TH, "text-right")}>
                <span className="sr-only">Action</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {jobs.length === 0 && (
              <tr>
                <td
                  colSpan={7}
                  className="px-4 py-10 text-center text-body-sm text-muted-foreground"
                >
                  {emptyLabel}
                </td>
              </tr>
            )}
            {jobs.map((job) => (
              <tr key={job.id}>
                <td className={TD}>
                  <JobStatusChip status={job.status} />
                </td>
                <td className={TD}>
                  <Link
                    href={`/hr/candidates/${job.candidate.id}`}
                    className="font-semibold text-primary-strong hover:text-primary-deep"
                  >
                    {job.candidate.name}
                  </Link>
                </td>
                <td className={TD}>{job.role.title}</td>
                <td className={TD}>
                  <span className="flex items-center gap-1.5">
                    {job.answer.kind === "audio" ? (
                      <Mic
                        className="size-3.5 text-muted-foreground"
                        aria-hidden
                      />
                    ) : (
                      <AlignLeft
                        className="size-3.5 text-muted-foreground"
                        aria-hidden
                      />
                    )}
                    {job.answer.question_id}
                  </span>
                </td>
                <td className={cn(TD, "max-w-[280px]")}>
                  <span
                    className="block truncate text-muted-foreground"
                    title={detail(job)}
                  >
                    {detail(job)}
                  </span>
                </td>
                <td className={cn(TD, "text-muted-foreground")}>
                  {formatRelative(job.updated_at)}
                </td>
                <td className={cn(TD, "text-right")}>
                  {job.status === "failed" ? (
                    <Button
                      size="sm"
                      onClick={() => onRetry(job)}
                      disabled={retrying !== null}
                    >
                      <RotateCw
                        className={
                          retrying === job.id
                            ? "motion-safe:animate-spin"
                            : undefined
                        }
                        aria-hidden
                      />
                      Retry
                    </Button>
                  ) : (
                    <Link
                      href={`/hr/candidates/${job.candidate.id}`}
                      className={cn(
                        buttonVariants({ size: "sm" }),
                        "text-meta",
                      )}
                    >
                      Review
                    </Link>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
