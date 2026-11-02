import { Check } from "lucide-react";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import type { AnswerReceipt } from "@/lib/api-types";
import { formatTime } from "@/lib/format-time";

interface AnswerReceiptViewProps {
  receipt: AnswerReceipt;
  /** Interview is closed after this answer — completion copy, no back button. */
  completed: boolean;
  total: number;
  onBack: () => void;
  onNext: () => void;
}

export function AnswerReceiptView({
  receipt,
  completed,
  total,
  onBack,
  onNext,
}: AnswerReceiptViewProps) {
  const kindLabel = receipt.kind === "audio" ? "Audio file" : "Typed answer";
  const detail = completed
    ? `That was the last question — all ${total} answers are saved.`
    : "Saved safely — you can close this page and come back with the same link.";

  return (
    <div className="flex flex-col gap-5">
      <Alert
        variant="success"
        role="status"
        className="flex items-start gap-3.5 px-5 py-4.5"
      >
        <span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-success">
          <Check
            className="size-4.5 text-success-foreground"
            strokeWidth={2.6}
            aria-hidden
          />
        </span>
        <div className="flex flex-col gap-1">
          <span className="font-bold text-body-lg text-success-ink-strong">
            Your answer arrived
          </span>
          <span className="text-body-sm leading-[1.5]">
            {kindLabel} received at {formatTime(receipt.received_at)}. {detail}
          </span>
        </div>
      </Alert>
      <div className="flex flex-wrap items-center justify-end gap-3">
        {!completed && (
          <Button variant="secondary" size="cta" onClick={onBack}>
            Back to this question
          </Button>
        )}
        <Button size="xl" onClick={onNext}>
          {completed ? "Finish" : "Next question →"}
        </Button>
      </div>
    </div>
  );
}
