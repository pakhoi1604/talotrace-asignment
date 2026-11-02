"use client";

// Right column of a question card, per panel state. Renders only what the API
// returned — a failed job shows no number in the score slot.

import { CircleAlert, Clock, RotateCw } from "lucide-react";

import {
  EarlierDecisionNotes,
  HrDecisionNote,
} from "@/components/hr/review/hr-decision-note";
import { ScoreFigure } from "@/components/hr/score-figure";
import { Button } from "@/components/ui/button";
import type { AnswerReview } from "@/lib/api-types";
import { formatTime } from "@/lib/hr-format";
import type { Panel } from "@/lib/hr-review-state";

const LBL =
  "font-semibold text-caption uppercase tracking-[0.04em] text-muted-foreground";

interface ScoreSidePanelProps {
  panel: Panel;
  answer: AnswerReview | null;
  pendingAction: string | null;
  /** True while the override form is open — the form replaces the action row. */
  hideActions: boolean;
  onAccept: () => void;
  onOpenOverride: () => void;
  onRetry: () => void;
}

export function ScoreSidePanel({
  panel,
  answer,
  pendingAction,
  hideActions,
  onAccept,
  onOpenOverride,
  onRetry,
}: ScoreSidePanelProps) {
  const pending = pendingAction !== null;

  const overrideButton = (primary: boolean, label = "Override") =>
    hideActions ? null : (
      <Button
        variant={primary ? "default" : "secondary"}
        size="lg"
        onClick={onOpenOverride}
        disabled={pending}
        className="self-start"
      >
        {label}
      </Button>
    );

  switch (panel.kind) {
    case "unanswered":
      return <p className="text-muted-foreground">Not answered yet</p>;

    case "queued":
      return (
        <>
          <div className="flex items-center gap-2.5 text-muted-foreground">
            <Clock className="size-5" aria-hidden />
            <span className="font-semibold text-body-lg">Scoring queued</span>
          </div>
          {panel.job && panel.job.attempts > 0 && (
            <p className="m-0 text-meta text-muted-foreground">
              attempt {panel.job.attempts}
            </p>
          )}
          {panel.job && (
            <p className="m-0 text-caption text-muted-foreground">
              Updated {formatTime(panel.job.updated_at)}
            </p>
          )}
          {overrideButton(false)}
        </>
      );

    case "scored":
      return (
        <>
          <ScoreFigure score={panel.score} label="suggested" />
          <div className="flex flex-col gap-1.5">
            <span className={LBL}>Reason</span>
            <p className="m-0 text-foreground-body text-meta">{panel.reason}</p>
          </div>
          {!hideActions && (
            <div className="flex flex-wrap gap-2">
              <Button size="lg" onClick={onAccept} disabled={pending}>
                Accept {panel.score}
              </Button>
              {overrideButton(false)}
            </div>
          )}
        </>
      );

    case "needs_person":
      return (
        <>
          {panel.suggested !== null && (
            <ScoreFigure score={panel.suggested} label="suggested" />
          )}
          <div className="flex flex-col gap-1.5">
            <span className={`${LBL} text-warning-ink`}>
              Why a person is needed
            </span>
            <p className="m-0 text-foreground-body text-meta">{panel.reason}</p>
          </div>
          {overrideButton(true)}
        </>
      );

    case "failed":
      return (
        <>
          <div className="flex items-center gap-2.5 text-danger-ink">
            <CircleAlert className="size-[22px]" aria-hidden />
            <span className="font-bold text-body-lg">No score yet</span>
          </div>
          {panel.job?.last_error && (
            <p className="m-0 text-foreground-body text-meta">
              {panel.job.last_error}
            </p>
          )}
          {panel.job && (
            <p className="m-0 text-foreground-body text-meta">
              {panel.job.attempts} attempt{panel.job.attempts === 1 ? "" : "s"}{" "}
              made
            </p>
          )}
          {panel.job && (
            <span className="text-caption text-danger-ink-strong">
              Last attempt {formatTime(panel.job.updated_at)} · job #
              {panel.job.id}
            </span>
          )}
          {!hideActions && (
            <div className="flex flex-wrap gap-2">
              <Button size="lg" onClick={onRetry} disabled={pending}>
                <RotateCw aria-hidden />
                Retry scoring
              </Button>
              {overrideButton(false)}
            </div>
          )}
        </>
      );

    case "decided": {
      const { decision } = panel;
      return (
        <>
          <ScoreFigure
            score={decision.score}
            label="final"
            tone="hr"
            suggested={panel.suggested}
          />
          {panel.reason && (
            <div className="flex flex-col gap-1.5">
              <span className={LBL}>Suggested reason</span>
              <p className="m-0 text-foreground-body text-meta">
                {panel.reason}
              </p>
            </div>
          )}
          <HrDecisionNote decision={decision} />
          <EarlierDecisionNotes decisions={answer?.decisions.slice(1) ?? []} />
          {!hideActions && (
            <div className="flex flex-wrap gap-2">
              {panel.job?.status === "failed" && (
                <Button size="lg" onClick={onRetry} disabled={pending}>
                  <RotateCw aria-hidden />
                  Retry scoring
                </Button>
              )}
              {overrideButton(false, "Edit override")}
            </div>
          )}
        </>
      );
    }
  }
}
