// Candidate interview endpoints. Shapes mirror docs/api-doc.md only — never
// infer from backend code. The token goes in the Authorization header only
// (never in a path, query, or log).

import { apiFetch } from "@/lib/api-client";
import type { AnswerReceipt, InterviewView } from "@/lib/api-types";

// mirrors docs/api-doc.md — UX guards only; the server stays the authority
export const MAX_TEXT_CHARS = 10_000;
export const MAX_AUDIO_BYTES = 25 * 1024 * 1024;
export const AUDIO_EXTENSIONS = [
  ".m4a",
  ".mp3",
  ".wav",
  ".webm",
  ".ogg",
  ".mp4",
] as const;

const auth = (token: string) => ({ Authorization: `Bearer ${token}` });

export const getInterview = (token: string) =>
  apiFetch<InterviewView>("/api/candidate/interview", {
    headers: auth(token),
    cache: "no-store",
  });

export const submitTextAnswer = (
  token: string,
  questionId: string,
  text: string,
) =>
  apiFetch<AnswerReceipt>(
    `/api/candidate/answers/${encodeURIComponent(questionId)}`,
    {
      method: "PUT",
      headers: { ...auth(token), "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    },
  );

// Some OS/browser combos label .m4a etc. as "" or application/octet-stream → server 415.
// Re-wrap with a type inferred from the extension (bytes unchanged, so replays still match).
const AUDIO_MIME_BY_EXT: Record<string, string> = {
  ".m4a": "audio/mp4",
  ".mp3": "audio/mpeg",
  ".wav": "audio/wav",
  ".webm": "audio/webm",
  ".ogg": "audio/ogg",
  ".mp4": "video/mp4",
};

export function withAudioMime(file: File): File {
  if (/^(audio\/|video\/(mp4|webm)$)/.test(file.type)) return file;
  const ext = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
  const type = AUDIO_MIME_BY_EXT[ext];
  return type ? new File([file], file.name, { type }) : file;
}

export function submitAudioAnswer(
  token: string,
  questionId: string,
  file: File,
) {
  const body = new FormData();
  body.append("file", withAudioMime(file));
  return apiFetch<AnswerReceipt>(
    `/api/candidate/answers/${encodeURIComponent(questionId)}/audio`,
    { method: "PUT", headers: auth(token), body },
  );
}
