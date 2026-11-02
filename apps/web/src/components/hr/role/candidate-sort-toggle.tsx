"use client";

// Segmented sort control: Name (default, API order) · Highest score · Newest.
// aria-pressed toggle buttons (one active at a time).

import { cn } from "cn";
import type { CandidateSort } from "@/lib/hr-role-stats";

const OPTIONS: { value: CandidateSort; label: string }[] = [
  { value: "name", label: "Name" },
  { value: "highest", label: "Highest score" },
  { value: "newest", label: "Newest" },
];

interface CandidateSortToggleProps {
  value: CandidateSort;
  onChange: (value: CandidateSort) => void;
}

export function CandidateSortToggle({
  value,
  onChange,
}: CandidateSortToggleProps) {
  return (
    <fieldset className="flex gap-1 rounded-md border-0 bg-muted p-1">
      <legend className="sr-only">Sort candidates</legend>
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
          </button>
        );
      })}
    </fieldset>
  );
}
