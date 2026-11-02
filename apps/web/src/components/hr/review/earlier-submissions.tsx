// Replaced submissions kept for the record — they don't count and take no new
// decisions, but their HR decision history stays visible.

import { AlignLeft, Mic } from "lucide-react";

import { AudioAnswerPlayer } from "@/components/hr/review/audio-answer-player";
import { HrDecisionNote } from "@/components/hr/review/hr-decision-note";
import type { EarlierSubmission } from "@/lib/api-types";
import { formatTime } from "@/lib/hr-format";

function Submission({ sub }: { sub: EarlierSubmission }) {
  const Icon = sub.kind === "audio" ? Mic : AlignLeft;
  return (
    <div className="flex flex-col gap-2 border-border-subtle border-t pt-2.5">
      <span className="flex items-center gap-1.5 text-meta text-muted-foreground">
        <Icon className="size-3.5" aria-hidden />
        {sub.kind === "audio" ? "Audio answer" : "Typed answer"} · received{" "}
        {formatTime(sub.submitted_at)}
        {sub.superseded_at && ` · replaced ${formatTime(sub.superseded_at)}`}
      </span>
      {sub.kind === "audio" && sub.audio ? (
        <AudioAnswerPlayer audio={sub.audio} receivedAt={sub.submitted_at} />
      ) : (
        <p className="m-0 max-w-[70ch] whitespace-pre-wrap text-foreground-body text-meta leading-[1.6]">
          {sub.text}
        </p>
      )}
      {sub.decisions.map((d) => (
        <HrDecisionNote key={d.id} decision={d} />
      ))}
    </div>
  );
}

export function EarlierSubmissions({
  submissions,
}: {
  submissions: EarlierSubmission[];
}) {
  if (submissions.length === 0) return null;
  return (
    <details className="text-meta text-muted-foreground">
      <summary className="cursor-pointer font-medium text-primary-strong">
        {submissions.length === 1
          ? `Show earlier submission (${formatTime(submissions[0].submitted_at)}, replaced)`
          : `Show ${submissions.length} earlier submissions`}
      </summary>
      <div className="mt-2.5 flex flex-col gap-3">
        {submissions.map((s) => (
          <Submission key={s.id} sub={s} />
        ))}
        <p className="m-0 text-caption">
          Kept for the record. They don't count and have no score.
        </p>
      </div>
    </details>
  );
}
