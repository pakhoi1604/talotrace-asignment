"use client";

// Filter chips for /hr/jobs: All · Queued · Scored · Failed · Needs a person ·
// Replaced, each with its count. aria-pressed buttons; the URL carries the
// filter so views are shareable.

import { cn } from "cn";
import type { JobCountsAll } from "@/lib/api-types";

/** Filters offered in the UI; "all" sends no status param, "queued" folds running in. */
export type JobFilter =
  | "all"
  | "queued"
  | "scored"
  | "failed"
  | "needs_person"
  | "superseded";

export function jobCount(counts: JobCountsAll, filter: JobFilter): number {
  if (filter === "all")
    return (
      counts.queued +
      counts.running +
      counts.scored +
      counts.failed +
      counts.needs_person +
      counts.superseded
    );
  if (filter === "queued") return counts.queued + counts.running;
  return counts[filter];
}

const OPTIONS: { value: JobFilter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "queued", label: "Queued" },
  { value: "scored", label: "Scored" },
  { value: "failed", label: "Failed" },
  { value: "needs_person", label: "Needs a person" },
  { value: "superseded", label: "Replaced" },
];

interface JobsFilterChipsProps {
  counts?: JobCountsAll;
  value: JobFilter;
  onChange: (value: JobFilter) => void;
}

export function JobsFilterChips({
  counts,
  value,
  onChange,
}: JobsFilterChipsProps) {
  return (
    <fieldset className="flex flex-wrap gap-1 rounded-md border-0 bg-muted p-1">
      <legend className="sr-only">Filter jobs by status</legend>
      {OPTIONS.map((option) => {
        const active = option.value === value;
        return (
          <button
            key={option.value}
            type="button"
            aria-pressed={active}
            onClick={() => onChange(option.value)}
            className={cn(
              "rounded-sm px-3 py-1.5 text-meta",
              active
                ? "bg-card font-semibold text-primary-strong shadow-control"
                : "font-medium text-muted-foreground",
            )}
          >
            {option.label}
            {counts && (
              <span className="ml-1.5 rounded-full bg-neutral-subtle px-1.5 font-semibold text-caption text-neutral-ink">
                {jobCount(counts, option.value)}
              </span>
            )}
          </button>
        );
      })}
    </fieldset>
  );
}
