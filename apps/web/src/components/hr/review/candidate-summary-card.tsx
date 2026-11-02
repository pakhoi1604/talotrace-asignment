"use client";

// Summary card on top of the review page: back link, identity + progress,
// averages, job chips, Refresh.

import { ChevronLeft } from "lucide-react";
import Link from "next/link";

import { JobCountsChips } from "@/components/hr/job-counts-chips";
import { RefreshButton } from "@/components/hr/refresh-button";
import type { CandidateReview } from "@/lib/api-types";
import { formatAvg, formatRelative, initials } from "@/lib/hr-format";

const LBL =
  "font-semibold text-caption uppercase tracking-[0.04em] text-muted-foreground";

interface CandidateSummaryCardProps {
  review: CandidateReview;
  lastActivityAt: string | null;
  refreshing: boolean;
  loadedAt?: Date;
  onRefresh: () => void;
}

export function CandidateSummaryCard({
  review,
  lastActivityAt,
  refreshing,
  loadedAt,
  onRefresh,
}: CandidateSummaryCardProps) {
  return (
    <>
      <Link
        href={`/hr/roles/${review.role.id}`}
        className="inline-flex items-center gap-1.5 self-start text-body-sm text-primary-strong hover:text-primary-deep"
      >
        <ChevronLeft className="size-4" aria-hidden />
        {review.role.title} · all candidates
      </Link>
      <section className="flex flex-wrap items-center justify-between gap-6 rounded-2xl border bg-card p-6">
        <div className="flex items-center gap-4">
          <div className="flex size-14 items-center justify-center rounded-full bg-primary-soft font-bold text-primary-strong text-title">
            {initials(review.name)}
          </div>
          <div className="flex flex-col gap-1">
            <h1 className="font-bold text-heading-lg">{review.name}</h1>
            <span className="text-body-sm text-muted-foreground">
              {review.role.title} · {review.answered_count} of{" "}
              {review.total_questions} answered
              {lastActivityAt &&
                ` · last answer ${formatRelative(lastActivityAt)}`}
            </span>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-7">
          <div className="flex flex-col gap-1">
            <span className={LBL}>Avg suggested</span>
            <span className="font-bold text-heading">
              {formatAvg(review.avg_suggested)}{" "}
              <span className="font-medium text-body-sm text-muted-foreground">
                / 4
              </span>
            </span>
          </div>
          <div className="flex flex-col gap-1">
            <span className={LBL}>Avg final (with HR)</span>
            <span className="font-bold text-heading text-primary-strong">
              {formatAvg(review.avg_final)}{" "}
              <span className="font-medium text-body-sm text-muted-foreground">
                / 4
              </span>
            </span>
          </div>
          <JobCountsChips counts={review.job_counts} />
          <RefreshButton
            refreshing={refreshing}
            loadedAt={loadedAt}
            onRefresh={onRefresh}
          />
        </div>
      </section>
    </>
  );
}
