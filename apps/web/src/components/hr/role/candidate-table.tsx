"use client";

// Candidate table for the role page: avatar + note, answer progress, averages,
// job chips, last activity, Review link. Scrolls horizontally below ~880px.

import { cn } from "cn";
import Link from "next/link";
import { JobCountsChips } from "@/components/hr/job-counts-chips";
import { CandidateSortToggle } from "@/components/hr/role/candidate-sort-toggle";
import { buttonVariants } from "@/components/ui/button";
import type { CandidateRow } from "@/lib/api-types";
import { formatAvg, formatRelative, initials } from "@/lib/hr-format";
import { type CandidateSort, candidateNote } from "@/lib/hr-role-stats";

const TH =
  "px-4 py-3 text-left text-caption font-semibold uppercase tracking-[0.04em] text-muted-foreground";
const TD = "border-b border-border-subtle px-4 py-4 align-middle text-body-sm";

interface CandidateTableProps {
  rows: CandidateRow[];
  totalQuestions: number;
  sort: CandidateSort;
  onSortChange: (sort: CandidateSort) => void;
}

export function CandidateTable({
  rows,
  totalQuestions,
  sort,
  onSortChange,
}: CandidateTableProps) {
  return (
    <section className="overflow-hidden rounded-2xl border bg-card">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b px-5 py-4">
        <h2 className="font-semibold text-body-lg">Candidates</h2>
        <CandidateSortToggle value={sort} onChange={onSortChange} />
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[880px] border-collapse">
          <thead className="bg-surface-subtle">
            <tr>
              <th scope="col" className={TH}>
                Candidate
              </th>
              <th scope="col" className={TH}>
                Answers
              </th>
              <th scope="col" className={TH}>
                Avg suggested
              </th>
              <th scope="col" className={TH}>
                Scoring jobs
              </th>
              <th scope="col" className={TH}>
                Last activity
              </th>
              <th scope="col" className={cn(TH, "text-right")}>
                <span className="sr-only">Action</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 && (
              <tr>
                <td
                  colSpan={6}
                  className="px-4 py-10 text-center text-body-sm text-muted-foreground"
                >
                  No candidates for this role yet.
                </td>
              </tr>
            )}
            {rows.map((c) => (
              <tr key={c.id}>
                <td className={TD}>
                  <div className="flex items-center gap-3">
                    <div className="flex size-9 items-center justify-center rounded-full bg-primary-soft font-semibold text-meta text-primary-strong">
                      {initials(c.name)}
                    </div>
                    <div className="flex flex-col gap-0.5">
                      <span className="font-semibold">{c.name}</span>
                      <span className="text-meta text-muted-foreground">
                        {candidateNote(c)}
                      </span>
                    </div>
                  </div>
                </td>
                <td className={TD}>
                  <div className="flex w-[120px] flex-col gap-1.5">
                    <span className="text-foreground-body text-meta">
                      {c.answered_count} of {totalQuestions}
                    </span>
                    <div className="h-1.5 overflow-hidden rounded-full bg-border">
                      <div
                        className="h-full rounded-full bg-primary"
                        style={{
                          width: `${(c.answered_count / totalQuestions) * 100}%`,
                        }}
                      />
                    </div>
                  </div>
                </td>
                <td className={TD}>
                  <span className="font-bold text-title">
                    {formatAvg(c.avg_suggested)}
                  </span>
                  <span className="text-muted-foreground"> / 4</span>
                  {c.avg_final !== null && c.avg_final !== c.avg_suggested && (
                    <span className="block font-semibold text-meta text-primary-strong">
                      final {formatAvg(c.avg_final)}
                    </span>
                  )}
                </td>
                <td className={TD}>
                  <JobCountsChips counts={c.job_counts} />
                </td>
                <td className={cn(TD, "text-muted-foreground")}>
                  {c.last_activity_at
                    ? formatRelative(c.last_activity_at)
                    : "—"}
                </td>
                <td className={cn(TD, "text-right")}>
                  <Link
                    href={`/hr/candidates/${c.id}`}
                    aria-label={`Review ${c.name}`}
                    className={cn(buttonVariants({ size: "lg" }), "text-meta")}
                  >
                    Review
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
