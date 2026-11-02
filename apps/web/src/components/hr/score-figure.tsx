// Big score figure: "3 / 4 suggested" (or "/ 4 final"). `tone="hr"` colors the
// number for HR-decided finals; `suggested` adds the struck-through suggestion
// the decision replaced.

import { cn } from "cn";

interface ScoreFigureProps {
  score: number;
  /** Label after "/ 4", e.g. "suggested" or "final". */
  label: string;
  tone?: "default" | "hr";
  /** Earlier suggestion to strike through ("final · 2 suggested"). */
  suggested?: number | null;
}

export function ScoreFigure({
  score,
  label,
  tone = "default",
  suggested = null,
}: ScoreFigureProps) {
  return (
    <div className="flex items-end gap-2.5">
      <span
        className={cn(
          "font-bold text-score",
          tone === "hr" && "text-primary-strong",
        )}
      >
        {score}
      </span>
      <span className="pb-0.5 text-body-sm text-muted-foreground">
        / 4 {label}
        {suggested !== null && (
          <>
            {" "}
            · <s>{suggested} suggested</s>
          </>
        )}
      </span>
    </div>
  );
}
