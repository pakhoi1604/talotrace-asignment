// "HR override" / "HR accepted" info chip shown next to the job status chip
// once an HR decision sets the final score.

import { Badge } from "@/components/ui/badge";
import type { DecisionKind } from "@/lib/api-types";

export function HrOverrideChip({ kind }: { kind: DecisionKind }) {
  return (
    <Badge variant="info">
      {kind === "accept" ? "HR accepted" : "HR override"}
    </Badge>
  );
}
