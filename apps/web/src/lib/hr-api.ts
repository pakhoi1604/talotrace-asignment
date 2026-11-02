// HR review endpoints. Shapes mirror docs/api-doc.md only — never infer from
// backend code. Auth is the httpOnly `hr_session` cookie (MOCK sign-in), sent
// automatically on same-origin requests through the /api rewrite.

import { apiFetch } from "@/lib/api-client";
import type {
  CandidateReview,
  DecisionView,
  HrSession,
  JobList,
  JobStatus,
  JobView,
  RoleCandidates,
  RoleList,
} from "@/lib/api-types";

// All HR POSTs must send Content-Type: application/json (415 otherwise).
const json = (body: unknown): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

const get = <T>(path: `/api/${string}`) =>
  apiFetch<T>(path, { cache: "no-store" });

export const signIn = (email: string, password: string) =>
  apiFetch<HrSession>("/api/hr/session", json({ email, password }));

export const getSession = () => get<HrSession>("/api/hr/session");

// 204, no body — apiFetch returns undefined without parsing.
export const signOut = () =>
  apiFetch<void>("/api/hr/session", { method: "DELETE" });

export const listRoles = () => get<RoleList>("/api/hr/roles");

export const getRoleCandidates = (roleId: number | string) =>
  get<RoleCandidates>(`/api/hr/roles/${encodeURIComponent(roleId)}/candidates`);

export const getCandidateReview = (id: string) =>
  get<CandidateReview>(`/api/hr/candidates/${encodeURIComponent(id)}`);

// `superseded` jobs are excluded by default; a status filters to exactly one.
export const listJobs = (status?: JobStatus) =>
  get<JobList>(`/api/hr/jobs${status ? `?status=${status}` : ""}`);

// Audio playback uses answer.audio.url as an <audio> src — never fetched in JS.

export const overrideScore = (
  answerId: string,
  score: number,
  reason: string,
) =>
  apiFetch<DecisionView>(
    `/api/hr/answers/${encodeURIComponent(answerId)}/override`,
    json({ score, reason }),
  );

export const acceptScore = (answerId: string, score: number) =>
  apiFetch<DecisionView>(
    `/api/hr/answers/${encodeURIComponent(answerId)}/accept`,
    json({ score }),
  );

export const retryJob = (jobId: number) =>
  apiFetch<JobView>(`/api/hr/jobs/${jobId}/retry`, json({}));
