import type { AnsweredItem } from "@/lib/api-types";

interface InterviewProgressProps {
  position: number;
  total: number;
  answered: AnsweredItem[];
}

export function InterviewProgress({
  position,
  total,
  answered,
}: InterviewProgressProps) {
  const answeredPositions = new Set(answered.map((a) => a.position));
  const segments = Array.from({ length: total }, (_, i) => i + 1);

  return (
    <div className="flex flex-col gap-2.5">
      <div className="flex justify-between font-semibold text-meta">
        <span className="text-primary-strong">
          Question {position} of {total}
        </span>
        <span className="text-muted-foreground">
          {answered.length} of {total} answered
        </span>
      </div>
      <div
        className="grid gap-1.5"
        style={{
          gridTemplateColumns: `repeat(${total}, minmax(0, 1fr))`,
        }}
        aria-hidden="true"
      >
        {segments.map((i) => (
          <div
            key={i}
            className={`h-1.5 rounded-full ${
              answeredPositions.has(i)
                ? "bg-primary"
                : i === position
                  ? "bg-primary-muted"
                  : "bg-border"
            }`}
          />
        ))}
      </div>
    </div>
  );
}
