"use client";

import { useParams } from "next/navigation";
import { useCallback, useEffect, useReducer } from "react";

import { AnswerForm } from "@/components/interview/answer-form";
import { AnswerReceiptView } from "@/components/interview/answer-receipt";
import { InterviewHeader } from "@/components/interview/interview-header";
import { InterviewMessageCard } from "@/components/interview/interview-message-card";
import { InterviewProgress } from "@/components/interview/interview-progress";
import { Button } from "@/components/ui/button";
import { ApiRequestError } from "@/lib/api-client";
import type {
  AnswerReceipt,
  CurrentQuestion,
  InterviewView,
} from "@/lib/api-types";
import {
  getInterview,
  submitAudioAnswer,
  submitTextAnswer,
} from "@/lib/candidate-api";
import { toCandidateMessage } from "@/lib/candidate-error-messages";
import { formatTime } from "@/lib/format-time";

type Screen =
  | "loading"
  | "invalid"
  | "loadError"
  | "answer"
  | "receipt"
  | "completed";

interface State {
  screen: Screen;
  view: InterviewView | null;
  /** Question being answered, or just answered on the receipt screen. */
  question: CurrentQuestion | null;
  receipt: AnswerReceipt | null;
  /** Text to prefill when reopening a just-submitted question. */
  prefill: string | undefined;
  error: string | null;
  pending: boolean;
}

type Action =
  | { type: "loaded"; view: InterviewView }
  | { type: "invalid" }
  | { type: "loadFailed"; message: string }
  | { type: "submitStart" }
  | { type: "submitted"; receipt: AnswerReceipt; text?: string }
  | { type: "submitFailed"; message: string }
  | { type: "resynced"; view: InterviewView; message: string }
  | { type: "viewRefreshed"; view: InterviewView }
  | { type: "back" };

const initial: State = {
  screen: "loading",
  view: null,
  question: null,
  receipt: null,
  prefill: undefined,
  error: null,
  pending: false,
};

function reducer(state: State, action: Action): State {
  switch (action.type) {
    case "loaded": {
      const { view } = action;
      if (view.completed || !view.current_question)
        return { ...initial, screen: "completed", view };
      return {
        ...initial,
        screen: "answer",
        view,
        question: view.current_question,
      };
    }
    case "invalid":
      return { ...initial, screen: "invalid" };
    case "loadFailed":
      return { ...initial, screen: "loadError", error: action.message };
    case "submitStart":
      return { ...state, pending: true, error: null };
    case "submitted":
      return {
        ...state,
        pending: false,
        screen: "receipt",
        receipt: action.receipt,
        prefill: action.text,
        error: null,
      };
    case "submitFailed":
      return { ...state, pending: false, error: action.message };
    case "resynced": {
      // Server disagreed about the open question — take its view.
      const { view } = action;
      if (view.completed || !view.current_question)
        return { ...initial, screen: "completed", view };
      return {
        ...state,
        pending: false,
        screen: "answer",
        view,
        question: view.current_question,
        prefill: undefined,
        error: action.message,
      };
    }
    case "viewRefreshed":
      return { ...state, view: action.view };
    case "back":
      return { ...state, screen: "answer", receipt: null, error: null };
    default:
      return state;
  }
}

const isAuthError = (err: unknown) =>
  err instanceof ApiRequestError && err.status === 401;

export function InterviewScreen() {
  const { token } = useParams<{ token: string }>();
  const [state, dispatch] = useReducer(reducer, initial);

  const load = useCallback(async () => {
    try {
      const view = await getInterview(token);
      dispatch({ type: "loaded", view });
    } catch (err) {
      if (isAuthError(err)) dispatch({ type: "invalid" });
      else dispatch({ type: "loadFailed", message: toCandidateMessage(err) });
    }
  }, [token]);

  useEffect(() => {
    void load();
  }, [load]);

  // Background refetch after a submit: updates counts/progress while the
  // receipt stays on screen (the receipt keeps its own question).
  const refreshView = useCallback(() => {
    getInterview(token)
      .then((view) => dispatch({ type: "viewRefreshed", view }))
      .catch(() => {});
  }, [token]);

  const handleSubmitError = useCallback(
    async (err: unknown) => {
      if (isAuthError(err)) {
        dispatch({ type: "invalid" });
        return;
      }
      if (err instanceof ApiRequestError && err.status === 409) {
        try {
          const view = await getInterview(token);
          dispatch({
            type: "resynced",
            view,
            message: toCandidateMessage(err),
          });
          return;
        } catch (refetchErr) {
          dispatch({
            type: "submitFailed",
            message: toCandidateMessage(refetchErr),
          });
          return;
        }
      }
      dispatch({ type: "submitFailed", message: toCandidateMessage(err) });
    },
    [token],
  );

  const onSubmitText = async (text: string): Promise<boolean> => {
    if (!state.question) return false;
    dispatch({ type: "submitStart" });
    try {
      const receipt = await submitTextAnswer(token, state.question.id, text);
      dispatch({ type: "submitted", receipt, text });
      refreshView();
      return true;
    } catch (err) {
      await handleSubmitError(err);
      return false;
    }
  };

  const onSubmitAudio = async (file: File): Promise<boolean> => {
    if (!state.question) return false;
    dispatch({ type: "submitStart" });
    try {
      const receipt = await submitAudioAnswer(token, state.question.id, file);
      dispatch({ type: "submitted", receipt });
      refreshView();
      return true;
    } catch (err) {
      await handleSubmitError(err);
      return false;
    }
  };

  // Refetch on Next so routing always follows the server state.
  const onNext = async () => {
    try {
      const view = await getInterview(token);
      dispatch({ type: "loaded", view });
    } catch (err) {
      if (isAuthError(err)) dispatch({ type: "invalid" });
      else dispatch({ type: "loadFailed", message: toCandidateMessage(err) });
    }
  };

  const { screen, view, question, receipt, prefill, error, pending } = state;

  // No view yet (or ever): loading / invalid link / load error.
  if (!view) {
    return (
      <div className="flex flex-1 flex-col bg-background">
        <main className="mx-auto flex w-full max-w-interview flex-1 items-center px-6 py-16">
          {screen === "loading" && (
            <InterviewMessageCard title="Loading your interview…">
              <p>One moment.</p>
            </InterviewMessageCard>
          )}
          {screen === "invalid" && (
            <InterviewMessageCard title="This link isn't valid">
              <p>
                The link may have expired or been replaced. Please check the
                link in your invitation email, or ask HR to send you a new one.
              </p>
            </InterviewMessageCard>
          )}
          {screen === "loadError" && (
            <InterviewMessageCard title="Something went wrong">
              <p>{error}</p>
              <div>
                <Button
                  variant="secondary"
                  size="cta"
                  onClick={() => void load()}
                >
                  Reload
                </Button>
              </div>
            </InterviewMessageCard>
          )}
        </main>
      </div>
    );
  }

  const firstName = view.candidate_name.split(" ")[0];

  return (
    <div className="flex flex-1 flex-col bg-background">
      <InterviewHeader
        role={view.role}
        firstName={firstName}
        savedCount={view.answered_count}
      />
      <main className="mx-auto flex w-full max-w-interview flex-1 flex-col gap-6 px-6 pt-8 pb-16">
        {screen === "completed" ? (
          <InterviewMessageCard title="You're all done">
            <p>
              Thanks, {firstName} — all {view.total_questions} answers are
              saved. Our HR team will review them and be in touch.
            </p>
            <ul className="flex flex-col gap-1.5 text-body-sm">
              {view.answered.map((a) => (
                <li key={a.question_id}>
                  Question {a.position} —{" "}
                  {a.kind === "audio" ? "audio" : "typed"} answer received at{" "}
                  {formatTime(a.received_at)}
                </li>
              ))}
            </ul>
          </InterviewMessageCard>
        ) : (
          question && (
            <>
              <InterviewProgress
                position={question.position}
                total={view.total_questions}
                answered={view.answered}
              />
              <section className="flex flex-col gap-6 rounded-3xl border bg-card p-6 shadow-card sm:p-8">
                <h1 className="font-bold text-heading">{question.text}</h1>
                {screen === "answer" ? (
                  // key remounts the form when the server resyncs us to a
                  // different question, so tab/file state can't leak across.
                  <AnswerForm
                    key={question.id}
                    token={token}
                    question={question}
                    prefill={prefill}
                    pending={pending}
                    error={error}
                    onSubmitText={onSubmitText}
                    onSubmitAudio={onSubmitAudio}
                  />
                ) : receipt ? (
                  <AnswerReceiptView
                    receipt={receipt}
                    completed={view.completed}
                    total={view.total_questions}
                    onBack={() => dispatch({ type: "back" })}
                    onNext={() => void onNext()}
                  />
                ) : null}
              </section>
            </>
          )
        )}
        <footer className="text-center text-meta text-muted-foreground leading-[1.6]">
          <p>
            Your answers are reviewed by our HR team. Questions? Reply to your
            invitation email.
          </p>
          <p>
            Demo: invitation emails are <strong>mocked</strong>. Links are
            printed by <code>make seed</code>.
          </p>
        </footer>
      </main>
    </div>
  );
}
