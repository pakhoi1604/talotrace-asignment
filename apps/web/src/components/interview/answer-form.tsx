"use client";

import { useState } from "react";

import { AudioAnswerDropzone } from "@/components/interview/audio-answer-dropzone";
import { TextAnswerField } from "@/components/interview/text-answer-field";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useLocalDraft } from "@/hooks/use-local-draft";
import type { CurrentQuestion } from "@/lib/api-types";
import { MAX_TEXT_CHARS } from "@/lib/candidate-api";

interface AnswerFormProps {
  token: string;
  question: CurrentQuestion;
  /** Just-submitted text, used to prefill on "Back to this question". */
  prefill?: string;
  pending: boolean;
  error: string | null;
  /** Resolve true when the server accepted the answer. */
  onSubmitText: (text: string) => Promise<boolean>;
  onSubmitAudio: (file: File) => Promise<boolean>;
}

export function AnswerForm({
  token,
  question,
  prefill,
  pending,
  error,
  onSubmitText,
  onSubmitAudio,
}: AnswerFormProps) {
  const draft = useLocalDraft(token, question.id, prefill ?? "");
  // Tab state and file live here, so switching tabs keeps both inputs.
  const [tab, setTab] = useState("text");
  const [file, setFile] = useState<File | null>(null);

  const canSubmit =
    !pending &&
    (tab === "text"
      ? draft.text.trim().length > 0 && draft.text.length <= MAX_TEXT_CHARS
      : file !== null);

  const submit = async () => {
    if (tab === "text") {
      if (await onSubmitText(draft.text)) draft.clear();
    } else if (file && (await onSubmitAudio(file))) {
      setFile(null);
    }
  };

  return (
    <div className="flex flex-col gap-5">
      <Tabs value={tab} onValueChange={setTab}>
        <TabsList
          aria-label="Answer type"
          className="h-auto gap-1 self-start p-1"
        >
          <TabsTrigger value="text" className="h-10 px-4">
            Type an answer
          </TabsTrigger>
          <TabsTrigger value="audio" className="h-10 px-4">
            Upload audio
          </TabsTrigger>
        </TabsList>
        <TabsContent value="text">
          <TextAnswerField
            id={`answer-${question.id}`}
            value={draft.text}
            onChange={draft.setText}
            disabled={pending}
          />
        </TabsContent>
        <TabsContent value="audio">
          <AudioAnswerDropzone
            id={`audio-${question.id}`}
            file={file}
            onSelect={setFile}
            onRemove={() => setFile(null)}
            disabled={pending}
          />
        </TabsContent>
      </Tabs>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <div className="flex flex-wrap items-center justify-end gap-3 pt-1">
        <Button size="xl" disabled={!canSubmit} onClick={() => void submit()}>
          {pending ? "Sending…" : "Submit answer"}
        </Button>
      </div>
    </div>
  );
}
