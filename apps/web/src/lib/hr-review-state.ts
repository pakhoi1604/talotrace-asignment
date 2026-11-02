// Which side-panel an answered question gets. Pure — reads only the API
// response. An HR decision wins over whatever the job is doing ("decided");
// a failed job never carries a score.

import type { AnswerReview, DecisionView, JobView } from "@/lib/api-types";

export type Panel =
  | { kind: "unanswered" }
  | { kind: "failed"; job: JobView | null }
  | {
      kind: "decided";
      decision: DecisionView;
      suggested: number | null;
      reason: string | null;
      job: JobView | null;
    }
  | {
      kind: "scored";
      score: number | null;
      reason: string;
      job: JobView | null;
    }
  | {
      kind: "needs_person";
      reason: string | null;
      suggested: number | null;
      job: JobView | null;
    }
  | { kind: "queued"; job: JobView | null };

export function panelFor(answer: AnswerReview | null): Panel {
  if (!answer) return { kind: "unanswered" };
  const job = answer.job;
  const decision = answer.decisions[0]; // newest first
  if (answer.final_source === "hr" && decision) {
    return {
      kind: "decided",
      decision,
      // Striking the suggestion only makes sense when HR replaced it (override);
      // an accept confirms the same number — nothing to strike.
      suggested:
        decision.kind === "override" ? (job?.suggested_score ?? null) : null,
      reason: job?.suggested_reason ?? null,
      job,
    };
  }
  if (!job) return { kind: "queued", job: null };
  switch (job.status) {
    case "failed":
      return { kind: "failed", job };
    case "scored":
      return {
        kind: "scored",
        score: job.suggested_score,
        reason: job.suggested_reason ?? "",
        job,
      };
    case "needs_person":
      return {
        kind: "needs_person",
        reason: job.needs_person_reason,
        suggested: job.suggested_score,
        job,
      };
    default:
      // queued, running — and a stray superseded renders honestly as its chip
      return { kind: "queued", job };
  }
}

/** Accept is only valid on a `scored` job with a visible suggestion and no HR decision. */
export function canAccept(answer: AnswerReview | null): boolean {
  return panelFor(answer).kind === "scored";
}
