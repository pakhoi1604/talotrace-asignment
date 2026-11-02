// Six stat cards: Candidates · Answers · Scored · Queued · Failed · Needs a
// person. The status cards use the job chip as their label; Failed and
// Needs-a-person cards carry their status border.

import { cn } from "cn";
import { JobStatusChip } from "@/components/hr/job-status-chip";
import type { RoleStats } from "@/lib/hr-role-stats";

function StatCard({
  label,
  value,
  className,
}: {
  label: React.ReactNode;
  value: number;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-col gap-1.5 rounded-xl border bg-card px-5 py-4.5",
        className,
      )}
    >
      {label}
      <span className="font-bold text-display-sm">{value}</span>
    </div>
  );
}

const PLAIN_LABEL = "text-meta text-muted-foreground";

export function RoleStatCards({ stats }: { stats: RoleStats }) {
  return (
    <div className="grid grid-cols-[repeat(auto-fit,minmax(170px,1fr))] gap-4">
      <StatCard
        label={<span className={PLAIN_LABEL}>Candidates</span>}
        value={stats.candidates}
      />
      <StatCard
        label={<span className={PLAIN_LABEL}>Answers</span>}
        value={stats.answers}
      />
      <StatCard
        label={<JobStatusChip status="scored" />}
        value={stats.scored}
      />
      <StatCard
        label={<JobStatusChip status="queued" />}
        value={stats.queued}
      />
      <StatCard
        label={<JobStatusChip status="failed" />}
        value={stats.failed}
        className="border-danger-border"
      />
      <StatCard
        label={<JobStatusChip status="needs_person" />}
        value={stats.needsPerson}
        className="border-warning-border"
      />
    </div>
  );
}
