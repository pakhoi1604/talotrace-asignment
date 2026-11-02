"use client";

// /hr/candidates/[candidateId] client root: data, one open override form at a
// time (drafts keyed by answer id so a Refresh keeps a half-typed reason),
// per-card error map, and the accept / retry / override action handlers.
// A 409 shows the friendly copy and refetches; a 401 redirects to sign-in.

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { CandidateSummaryCard } from "@/components/hr/review/candidate-summary-card";
import type { OverrideDraft } from "@/components/hr/review/override-form";
import { QuestionReviewCard } from "@/components/hr/review/question-review-card";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { useHrResource } from "@/hooks/use-hr-resource";
import { ApiRequestError } from "@/lib/api-client";
import type { AnswerReview } from "@/lib/api-types";
import {
  acceptScore,
  getCandidateReview,
  overrideScore,
  retryJob,
} from "@/lib/hr-api";
import { useHrUnauthorizedRedirect } from "@/lib/hr-auth-redirect";
import { toHrMessage } from "@/lib/hr-error-messages";
import { panelFor } from "@/lib/hr-review-state";

export function CandidateReviewScreen() {
  const { candidateId } = useParams<{ candidateId: string }>();
  const review = useHrResource(
    () => getCandidateReview(candidateId),
    [candidateId],
  );
  const onUnauthorized = useHrUnauthorizedRedirect();
  const [openOverrideFor, setOpenOverrideFor] = useState<string | null>(null);
  const [drafts, setDrafts] = useState<Record<string, OverrideDraft>>({});
  const [pendingAction, setPendingAction] = useState<string | null>(null);
  const [cardErrors, setCardErrors] = useState<Record<string, string>>({});

  // Drop drafts/forms for answers that disappeared (e.g. superseded on reload).
  useEffect(() => {
    const ids = new Set(
      review.data?.questions.flatMap((q) => (q.answer ? [q.answer.id] : [])),
    );
    setDrafts((prev) =>
      Object.fromEntries(Object.entries(prev).filter(([id]) => ids.has(id))),
    );
    if (openOverrideFor && !ids.has(openOverrideFor)) setOpenOverrideFor(null);
  }, [review.data, openOverrideFor]);

  async function runAction(
    answerId: string,
    key: string,
    fn: () => Promise<unknown>,
  ) {
    setPendingAction(key);
    setCardErrors((prev) => {
      const next = { ...prev };
      delete next[answerId];
      return next;
    });
    try {
      await fn();
      setOpenOverrideFor(null);
      setDrafts((prev) => {
        const next = { ...prev };
        delete next[answerId];
        return next;
      });
      await review.reload();
    } catch (err) {
      if (onUnauthorized(err)) return;
      setCardErrors((prev) => ({ ...prev, [answerId]: toHrMessage(err) }));
      if (err instanceof ApiRequestError && err.status === 409)
        await review.reload(); // every 409 copy says "we've reloaded"
    } finally {
      setPendingAction(null);
    }
  }

  function openOverride(answer: AnswerReview) {
    setOpenOverrideFor(answer.id);
    setDrafts((prev) =>
      prev[answer.id]
        ? prev
        : {
            ...prev,
            [answer.id]: {
              score: answer.final_score ?? answer.job?.suggested_score ?? null,
              reason:
                answer.decisions[0]?.kind === "override"
                  ? (answer.decisions[0].reason ?? "")
                  : "",
            },
          },
    );
  }

  function closeOverride(answerId: string) {
    setOpenOverrideFor(null);
    setDrafts((prev) => {
      const next = { ...prev };
      delete next[answerId];
      return next;
    });
  }

  if (review.status === 404) {
    return (
      <Card className="mx-auto mt-16 w-full max-w-md">
        <CardHeader>
          <CardTitle>This candidate doesn't exist</CardTitle>
          <CardDescription>
            They may have been removed.{" "}
            <Link
              href="/hr"
              className="text-primary-strong hover:text-primary-deep"
            >
              Back to open roles
            </Link>
          </CardDescription>
        </CardHeader>
      </Card>
    );
  }

  if (review.error) {
    return (
      <Alert variant="destructive" className="mt-8">
        <AlertTitle>Couldn't load the review</AlertTitle>
        <AlertDescription>
          {review.error}
          <Button
            variant="secondary"
            size="sm"
            className="ml-3"
            onClick={() => void review.reload()}
          >
            Retry
          </Button>
        </AlertDescription>
      </Alert>
    );
  }

  if (review.loading || !review.data) {
    return (
      <div className="flex flex-col gap-5" aria-busy="true">
        <div className="h-24 animate-pulse rounded-2xl bg-muted" />
        {["q1", "q2", "q3"].map((k) => (
          <div key={k} className="h-64 animate-pulse rounded-2xl bg-muted" />
        ))}
      </div>
    );
  }

  const data = review.data;
  const lastActivityAt = data.questions.reduce<string | null>(
    (max, q) =>
      q.answer && (!max || q.answer.submitted_at > max)
        ? q.answer.submitted_at
        : max,
    null,
  );

  return (
    <div className="flex flex-col gap-5">
      <CandidateSummaryCard
        review={data}
        lastActivityAt={lastActivityAt}
        refreshing={review.refreshing}
        loadedAt={review.loadedAt}
        onRefresh={() => void review.reload()}
      />
      {data.questions.map((qr) => {
        const answer = qr.answer;
        const panel = panelFor(answer);
        const open = openOverrideFor !== null && openOverrideFor === answer?.id;
        return (
          <QuestionReviewCard
            key={qr.question.id}
            qr={qr}
            total={data.total_questions}
            panel={panel}
            overrideOpen={open}
            draft={answer ? drafts[answer.id] : undefined}
            error={answer ? cardErrors[answer.id] : undefined}
            pendingAction={pendingAction}
            onOpenOverride={() => answer && openOverride(answer)}
            onCancelOverride={() => answer && closeOverride(answer.id)}
            onDraftChange={(draft) =>
              answer && setDrafts((prev) => ({ ...prev, [answer.id]: draft }))
            }
            onAccept={() =>
              answer &&
              panel.kind === "scored" &&
              void runAction(answer.id, `accept:${answer.id}`, () =>
                acceptScore(answer.id, panel.score),
              )
            }
            onRetry={() => {
              const job = answer?.job;
              if (answer && job)
                void runAction(answer.id, `retry:${job.id}`, () =>
                  retryJob(job.id),
                );
            }}
            onSaveOverride={() => {
              const draft = answer ? drafts[answer.id] : undefined;
              const score = draft?.score;
              if (answer && draft && score !== null && score !== undefined)
                void runAction(answer.id, `override:${answer.id}`, () =>
                  overrideScore(answer.id, score, draft.reason.trim()),
                );
            }}
          />
        );
      })}
    </div>
  );
}
