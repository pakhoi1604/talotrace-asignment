// Derived values for /hr/roles/[roleId]. Pure — every number comes from the
// API response; notes describe job counts, never invented reasons.

import type { CandidateRow, RoleCandidates } from "@/lib/api-types";

export interface RoleStats {
  candidates: number;
  answers: number;
  scored: number;
  queued: number;
  failed: number;
  needsPerson: number;
}

export function roleStats(rc: RoleCandidates): RoleStats {
  const stats = {
    candidates: rc.candidates.length,
    answers: 0,
    scored: 0,
    queued: 0,
    failed: 0,
    needsPerson: 0,
  };
  for (const c of rc.candidates) {
    stats.answers += c.answered_count;
    stats.scored += c.job_counts.scored;
    stats.queued += c.job_counts.queued + c.job_counts.running;
    stats.failed += c.job_counts.failed;
    stats.needsPerson += c.job_counts.needs_person;
  }
  return stats;
}

const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? "" : "s"}`;

/** One-line note under the candidate's name, derived from returned counts only. */
export function candidateNote(c: CandidateRow): string {
  if (c.job_counts.failed > 0)
    return `${plural(c.job_counts.failed, "answer")} failed to score`;
  if (c.job_counts.needs_person > 0)
    return `${plural(c.job_counts.needs_person, "answer")} need${c.job_counts.needs_person === 1 ? "s" : ""} a person`;
  if (c.job_counts.queued + c.job_counts.running > 0)
    return "Scoring in progress";
  if (c.answered_count === 0) return "No answers yet";
  if (c.answered_count < c.total_questions)
    return `${c.answered_count} of ${c.total_questions} answered`;
  return "All answers scored";
}

export type CandidateSort = "name" | "highest" | "newest";

const byName = (a: CandidateRow, b: CandidateRow) =>
  a.name.localeCompare(b.name);

export function sortCandidates(
  rows: CandidateRow[],
  mode: CandidateSort,
): CandidateRow[] {
  if (mode === "name") return rows; // API already sorts by name
  return [...rows].sort((a, b) => {
    if (mode === "highest") {
      const av = a.avg_final ?? a.avg_suggested;
      const bv = b.avg_final ?? b.avg_suggested;
      if (av === null && bv === null) return byName(a, b);
      if (av === null) return 1;
      if (bv === null) return -1;
      return bv - av || byName(a, b);
    }
    // newest: last_activity_at desc, nulls last, tie → name
    const at = a.last_activity_at;
    const bt = b.last_activity_at;
    if (at === null && bt === null) return byName(a, b);
    if (at === null) return 1;
    if (bt === null) return -1;
    return bt.localeCompare(at) || byName(a, b);
  });
}
