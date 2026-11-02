// Pill for a scoring-job status with the design's colored dot.
// The API's `running` displays as "Queued" (the brief's four statuses);
// `superseded` shows as "Replaced". `count` renders "4 scored" style.

import { Badge } from "@/components/ui/badge";
import type { JobStatus } from "@/lib/api-types";
import { displayStatus } from "@/lib/hr-format";

const CHIP: Record<
  JobStatus,
  { variant: "success" | "neutral" | "danger" | "warning"; label: string }
> = {
  scored: { variant: "success", label: "Scored" },
  queued: { variant: "neutral", label: "Queued" },
  running: { variant: "neutral", label: "Queued" },
  failed: { variant: "danger", label: "Failed" },
  needs_person: { variant: "warning", label: "Needs a person" },
  superseded: { variant: "neutral", label: "Replaced" },
};

interface JobStatusChipProps {
  status: JobStatus;
  count?: number;
}

export function JobStatusChip({ status, count }: JobStatusChipProps) {
  const chip = CHIP[displayStatus(status)];
  return (
    <Badge variant={chip.variant}>
      <span className="size-1.5 rounded-full bg-current" aria-hidden />
      {count === undefined
        ? chip.label
        : `${count} ${chip.label.toLowerCase()}`}
    </Badge>
  );
}
