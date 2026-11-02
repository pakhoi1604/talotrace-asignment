// Count chips for a JobCounts object: scored always shown, the others only
// when non-zero; queued folds `running` in. Used in candidate tables and the
// review summary.

import { JobStatusChip } from "@/components/hr/job-status-chip";
import type { JobCounts } from "@/lib/api-types";

export function JobCountsChips({ counts }: { counts: JobCounts }) {
  const queued = counts.queued + counts.running;
  return (
    <div className="flex flex-wrap gap-1.5">
      <JobStatusChip status="scored" count={counts.scored} />
      {queued > 0 && <JobStatusChip status="queued" count={queued} />}
      {counts.failed > 0 && (
        <JobStatusChip status="failed" count={counts.failed} />
      )}
      {counts.needs_person > 0 && (
        <JobStatusChip status="needs_person" count={counts.needs_person} />
      )}
    </div>
  );
}
