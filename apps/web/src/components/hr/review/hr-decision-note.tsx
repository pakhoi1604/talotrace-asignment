// The HR decision box in a decided panel: who decided, when, and the reason
// (accepts have none). Earlier decisions collapse under a <details>.

import type { DecisionView } from "@/lib/api-types";
import { formatDateTime } from "@/lib/hr-format";

function label(d: DecisionView): string {
  return d.kind === "accept"
    ? `Accepted by ${d.hr_email}`
    : `HR reason · ${d.hr_email}`;
}

export function HrDecisionNote({ decision }: { decision: DecisionView }) {
  return (
    <div className="flex flex-col gap-1.5 rounded-md bg-primary-soft p-3">
      <span className="font-semibold text-caption text-primary-ink uppercase tracking-[0.04em]">
        {label(decision)} · {formatDateTime(decision.created_at)}
      </span>
      {decision.reason && (
        <p className="m-0 text-foreground-body text-meta">{decision.reason}</p>
      )}
    </div>
  );
}

export function EarlierDecisionNotes({
  decisions,
}: {
  decisions: DecisionView[];
}) {
  if (decisions.length === 0) return null;
  return (
    <details className="text-meta text-muted-foreground">
      <summary className="cursor-pointer font-medium text-primary-strong">
        Earlier HR decisions ({decisions.length})
      </summary>
      <div className="mt-2 flex flex-col gap-2">
        {decisions.map((d) => (
          <HrDecisionNote key={d.id} decision={d} />
        ))}
      </div>
    </details>
  );
}
