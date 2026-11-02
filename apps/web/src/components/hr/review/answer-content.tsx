// Left column body: answer kind meta line, optional "Submitted N×" pill,
// the typed text or the audio player. Text is plain — the injection-highlight
// mockup element is dropped (the API doesn't return the span).

import { AlignLeft } from "lucide-react";

import { AudioAnswerPlayer } from "@/components/hr/review/audio-answer-player";
import type { AnswerReview } from "@/lib/api-types";
import { formatTime } from "@/lib/hr-format";

export function AnswerContent({ answer }: { answer: AnswerReview }) {
  return (
    <div className="flex flex-col gap-2.5">
      <div className="flex flex-wrap items-center gap-2.5 text-meta text-muted-foreground">
        <AlignLeft className="size-3.5" aria-hidden />
        <span>
          {answer.kind === "audio" ? "Audio answer" : "Typed answer"} · received{" "}
          {formatTime(answer.submitted_at)}
        </span>
        {answer.submission_count > 1 && (
          <span className="rounded-full bg-primary-soft px-2.5 py-0.5 font-semibold text-caption text-primary-ink">
            Submitted {answer.submission_count}× · this one counts
          </span>
        )}
      </div>
      {answer.kind === "audio" && answer.audio ? (
        <AudioAnswerPlayer
          audio={answer.audio}
          receivedAt={answer.submitted_at}
        />
      ) : (
        <p className="max-w-[70ch] whitespace-pre-wrap text-body-sm text-foreground-body leading-[1.65]">
          {answer.text}
        </p>
      )}
    </div>
  );
}
