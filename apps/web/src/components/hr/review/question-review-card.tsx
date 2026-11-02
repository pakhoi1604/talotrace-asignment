"use client";

// One question card: answer column (left) + score/decision side panel (right).
// The side stacks under the answer below ~900px (flex-wrap, as in the mockup).
// Card/side tones follow the panel state; an open override form highlights the
// card border + focus shadow.

import { cn } from "cn";
import { HrOverrideChip } from "@/components/hr/hr-override-chip";
import { JobStatusChip } from "@/components/hr/job-status-chip";
import { AnswerContent } from "@/components/hr/review/answer-content";
import { EarlierSubmissions } from "@/components/hr/review/earlier-submissions";
import { GradingGuide } from "@/components/hr/review/grading-guide";
import {
  type OverrideDraft,
  OverrideForm,
} from "@/components/hr/review/override-form";
import { ScoreSidePanel } from "@/components/hr/review/score-side-panel";
import { Alert, AlertDescription } from "@/components/ui/alert";
import type { QuestionReview } from "@/lib/api-types";
import type { Panel } from "@/lib/hr-review-state";

interface QuestionReviewCardProps {
  qr: QuestionReview;
  total: number;
  panel: Panel;
  overrideOpen: boolean;
  draft?: OverrideDraft;
  error?: string;
  pendingAction: string | null;
  onOpenOverride: () => void;
  onCancelOverride: () => void;
  onDraftChange: (draft: OverrideDraft) => void;
  onAccept: () => void;
  onRetry: () => void;
  onSaveOverride: () => void;
}

export function QuestionReviewCard({
  qr,
  total,
  panel,
  overrideOpen,
  draft,
  error,
  pendingAction,
  onOpenOverride,
  onCancelOverride,
  onDraftChange,
  onAccept,
  onRetry,
  onSaveOverride,
}: QuestionReviewCardProps) {
  const { question, answer } = qr;
  const decided = panel.kind === "decided" ? panel.decision : null;
  const titleId = `q-${question.id}`;

  const warning = panel.kind === "needs_person";
  const danger = panel.kind === "failed";

  return (
    <article
      aria-labelledby={titleId}
      className={cn(
        "flex flex-wrap overflow-hidden rounded-2xl border bg-card",
        warning && "border-warning-border",
        danger && "border-danger-border",
        overrideOpen && "border-primary-muted shadow-focus",
      )}
    >
      <div className="flex min-w-0 flex-[999_1_520px] flex-col gap-3 p-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <span className="font-bold text-caption text-primary-strong uppercase tracking-[0.05em]">
            Question {question.position} of {total}
          </span>
          <div className="flex gap-1.5">
            {answer && (
              <JobStatusChip status={answer.job?.status ?? "queued"} />
            )}
            {decided && <HrOverrideChip kind={decided.kind} />}
          </div>
        </div>
        <p
          id={titleId}
          className="m-0 font-semibold text-body-lg leading-[1.45]"
        >
          {question.text}
        </p>
        <GradingGuide rubric={question.rubric} />
        {answer && <AnswerContent answer={answer} />}
        {answer && (
          <EarlierSubmissions submissions={answer.earlier_submissions} />
        )}
      </div>
      <div
        className={cn(
          "flex flex-[1_1_340px] flex-col gap-3.5 border-l bg-surface-subtle p-6",
          warning && "border-warning-border bg-warning-soft",
          danger && "border-danger-border bg-danger-soft",
        )}
      >
        {error && (
          <Alert variant="destructive">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}
        <ScoreSidePanel
          panel={panel}
          answer={answer}
          pendingAction={pendingAction}
          hideActions={overrideOpen}
          onAccept={onAccept}
          onOpenOverride={onOpenOverride}
          onRetry={onRetry}
        />
        {overrideOpen && answer && draft && (
          <OverrideForm
            draft={draft}
            onChange={onDraftChange}
            onSave={onSaveOverride}
            onCancel={onCancelOverride}
            pending={pendingAction !== null}
          />
        )}
      </div>
    </article>
  );
}
