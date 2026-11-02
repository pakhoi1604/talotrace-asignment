// Collapsed grading guide under the question text: rubric 1–4.
// Not in the mockup; added so HR can judge against the same guide the model used.

import type { QuestionRef } from "@/lib/api-types";

export function GradingGuide({ rubric }: { rubric: QuestionRef["rubric"] }) {
  const entries = ["1", "2", "3", "4"].filter((k) => rubric[k]);
  if (entries.length === 0) return null;
  return (
    <details className="text-meta text-muted-foreground">
      <summary className="cursor-pointer font-medium text-primary-strong">
        Grading guide
      </summary>
      <dl className="mt-2 flex flex-col gap-1.5">
        {entries.map((score) => (
          <div key={score} className="flex gap-2">
            <dt className="shrink-0 font-semibold text-foreground-body">
              {score}
            </dt>
            <dd className="m-0">{rubric[score]}</dd>
          </div>
        ))}
      </dl>
    </details>
  );
}
