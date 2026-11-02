"use client";

// Override form: 4 radio score tiles + required reason (≤ 2000 chars) +
// Cancel/Save. Draft state lives in the screen (keyed by answer id) so a
// Refresh doesn't wipe a half-typed reason.

import { cn } from "cn";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

export interface OverrideDraft {
  score: number | null;
  reason: string;
}

export const MAX_REASON_CHARS = 2000;

interface OverrideFormProps {
  draft: OverrideDraft;
  onChange: (draft: OverrideDraft) => void;
  onSave: () => void;
  onCancel: () => void;
  pending: boolean;
}

export function OverrideForm({
  draft,
  onChange,
  onSave,
  onCancel,
  pending,
}: OverrideFormProps) {
  const [error, setError] = useState<string>();

  function submit(event: React.FormEvent) {
    event.preventDefault();
    if (draft.score === null) {
      setError("Pick a score from 1 to 4.");
      return;
    }
    if (!draft.reason.trim()) {
      setError("Please give a reason for the override.");
      return;
    }
    setError(undefined);
    onSave();
  }

  return (
    <form
      onSubmit={submit}
      noValidate
      className="flex flex-col gap-3 rounded-lg border-primary-border bg-card p-4"
    >
      <span className="font-semibold text-body-sm">Override score</span>
      <fieldset className="m-0 flex gap-2 border-0 p-0">
        <legend className="sr-only">New score</legend>
        {[1, 2, 3, 4].map((score) => {
          const checked = draft.score === score;
          return (
            <label
              key={score}
              className={cn(
                "flex h-11 flex-1 cursor-pointer items-center justify-center rounded-tab font-semibold",
                checked
                  ? "border-2 border-primary bg-primary-soft font-bold text-primary-strong"
                  : "border border-input text-muted-foreground",
              )}
            >
              <input
                type="radio"
                name="override-score"
                value={score}
                checked={checked}
                onChange={() => onChange({ ...draft, score })}
                className="sr-only"
              />
              {score}
            </label>
          );
        })}
      </fieldset>
      <div className="flex flex-col gap-1.5">
        <label htmlFor="override-reason" className="font-medium text-meta">
          Reason <span className="text-danger">(required)</span>
        </label>
        <Textarea
          id="override-reason"
          rows={3}
          required
          maxLength={MAX_REASON_CHARS}
          value={draft.reason}
          onChange={(e) => onChange({ ...draft, reason: e.target.value })}
          className="resize-y text-meta"
        />
        <span className="self-end text-caption text-muted-foreground">
          {draft.reason.length} / {MAX_REASON_CHARS}
        </span>
      </div>
      {error && (
        <p role="alert" className="m-0 text-danger-ink text-meta">
          {error}
        </p>
      )}
      <div className="flex justify-end gap-2">
        <Button
          type="button"
          variant="secondary"
          size="lg"
          onClick={onCancel}
          disabled={pending}
        >
          Cancel
        </Button>
        <Button type="submit" size="lg" disabled={pending}>
          {pending ? "Saving…" : "Save override"}
        </Button>
      </div>
    </form>
  );
}
