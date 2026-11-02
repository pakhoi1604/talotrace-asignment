// Friendly HR-facing copy for documented API errors.
// Keys are the exact `detail` strings from docs/api-doc.md; lookup order is
// detail → status → raw detail. Network failures get their own message.

import { ApiRequestError } from "@/lib/api-client";

export const NETWORK_MESSAGE =
  "Couldn't reach the server. Check that the API is running.";

/** Every 409 copy asks for fresh data — callers refetch after any 409. */
export const RELOAD_ON_409 = true;

const BY_DETAIL: Record<string, string> = {
  "invalid email or password": "Email or password is incorrect.",
  "hr sign-in is not configured":
    "HR sign-in isn't set up. Set HR_EMAIL and HR_PASSWORD in apps/api/.env.",
  "answer has been replaced by a newer submission":
    "The candidate sent a newer answer. We've reloaded it, so please review again.",
  "no suggested score to accept": "There's no suggested score to accept yet.",
  "needs a person: use override with a reason":
    "This answer needs a person. Use Override and give a reason.",
  "suggested score has changed, reload and try again":
    "The suggested score changed. We've reloaded the latest.",
  "another decision for this answer was just saved, reload and try again":
    "Someone just saved a decision for this answer. We've reloaded it.",
  "only failed jobs can be retried":
    "This job is no longer failed. We've reloaded its status.",
  "reason: must not be blank": "Please give a reason for the override.",
  "reason: must be at most 2000 characters":
    "Keep the reason under 2,000 characters.",
};

const BY_STATUS: Record<number, string> = {
  404: "Not found. It may have been removed.",
};

export function toHrMessage(err: unknown): string {
  if (err instanceof ApiRequestError) {
    return BY_DETAIL[err.message] ?? BY_STATUS[err.status] ?? err.message;
  }
  return NETWORK_MESSAGE;
}
