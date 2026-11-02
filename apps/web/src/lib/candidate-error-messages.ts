// Friendly candidate-facing copy for documented API errors.
// Keys are the exact `detail` strings from docs/api-doc.md; lookup order is
// detail → status → raw detail. Network failures get their own message.

import { ApiRequestError } from "@/lib/api-client";

export const NETWORK_MESSAGE =
  "Couldn't reach the server. Your draft is still on this device.";

const BY_DETAIL: Record<string, string> = {
  "answer the current question first":
    "This question isn't open yet. We've taken you back to your current question.",
  "interview is closed":
    "Your interview is already complete, so answers can't be changed.",
  "another submission for this question is in progress, please retry":
    "We're still saving another answer to this question. Please try again in a moment.",
  "question not found":
    "This question is no longer available. Please reload the page.",
  "text: must not be blank": "Please write an answer before submitting.",
  "text: Field required": "Please write an answer before submitting.",
  "body: Field required": "Please write an answer before submitting.",
  "text: must be at most 10000 characters":
    "Your answer is too long. Please keep it under 10,000 characters.",
  "audio file too large (max 25 MB)":
    "That file is larger than 25 MB. Please upload a shorter recording.",
  "unsupported audio type":
    "That file type isn't supported. Please use MP3, M4A, WAV, WebM, OGG or MP4.",
  "audio file is empty": "Please choose an audio file before submitting.",
  "file: Field required": "Please choose an audio file before submitting.",
};

const BY_STATUS: Record<number, string> = {
  413: BY_DETAIL["audio file too large (max 25 MB)"],
  415: BY_DETAIL["unsupported audio type"],
};

export function toCandidateMessage(err: unknown): string {
  if (err instanceof ApiRequestError) {
    return BY_DETAIL[err.message] ?? BY_STATUS[err.status] ?? err.message;
  }
  return NETWORK_MESSAGE;
}
