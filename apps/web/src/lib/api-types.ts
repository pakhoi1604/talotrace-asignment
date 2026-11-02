// Types mirrored from docs/api-doc.md — the single source of truth.
// Do not infer shapes from backend code; update this file when api-doc.md changes.

/** GET /api/health → 200 */
export interface HealthResponse {
  status: string;
  db: string;
}

/** Shared error shape for all endpoints. */
export interface ApiError {
  detail: string;
}

export type AnswerKind = "text" | "audio";

export interface CurrentQuestion {
  id: string;
  position: number;
  text: string;
}

export interface AnsweredItem {
  question_id: string;
  position: number;
  kind: AnswerKind;
  received_at: string;
}

/** GET /api/candidate/interview → 200 */
export interface InterviewView {
  candidate_name: string;
  role: string;
  total_questions: number;
  answered_count: number;
  completed: boolean;
  current_question: CurrentQuestion | null;
  answered: AnsweredItem[];
}

/** PUT /api/candidate/answers/{question_id} request body */
export interface TextAnswerRequest {
  text: string;
}

/** PUT /api/candidate/answers/{question_id}[/audio] → 201 | 200 */
export interface AnswerReceipt {
  answer_id: string;
  question_id: string;
  kind: AnswerKind;
  received_at: string;
  status: "received";
}

/** POST /api/hr/session request body (MOCK sign-in) */
export interface HrSignInRequest {
  email: string;
  password: string;
}

/** POST|GET /api/hr/session → 200 */
export interface HrSession {
  email: string;
  expires_at: string;
}

/* ---------- HR review (hr_session cookie) ---------- */

export type JobStatus =
  | "queued"
  | "running"
  | "scored"
  | "failed"
  | "needs_person"
  | "superseded";

/** Counts over current answers' jobs — superseded never counted. */
export interface JobCounts {
  queued: number;
  running: number;
  scored: number;
  failed: number;
  needs_person: number;
}

export interface JobCountsAll extends JobCounts {
  superseded: number;
}

export interface RoleRef {
  id: number;
  title: string;
}

/** GET /api/hr/roles item */
export interface RoleSummary {
  id: number;
  title: string;
  candidate_count: number;
  job_counts: JobCounts;
}

/** GET /api/hr/roles → 200 */
export interface RoleList {
  roles: RoleSummary[];
}

/** GET /api/hr/roles/{role_id}/candidates row */
export interface CandidateRow {
  id: string;
  name: string;
  answered_count: number;
  total_questions: number;
  avg_suggested: number | null;
  avg_final: number | null;
  job_counts: JobCounts;
  last_activity_at: string | null;
}

/** GET /api/hr/roles/{role_id}/candidates → 200 */
export interface RoleCandidates {
  role: RoleRef;
  total_questions: number;
  candidates: CandidateRow[];
}

/** Audio playback pointer; content_type comes from the file extension. */
export interface AudioMeta {
  content_type: string | null;
  size_bytes: number;
  url: string;
}

/** Scoring job as embedded in an answer review. */
export interface JobView {
  id: number;
  status: JobStatus;
  attempts: number;
  last_error: string | null;
  suggested_score: number | null;
  suggested_reason: string | null;
  needs_person_reason: string | null;
  model: string | null;
  updated_at: string;
}

/** Append-only HR decision, newest first in lists. */
export interface DecisionView {
  id: number;
  answer_id: string;
  kind: DecisionKind;
  score: number;
  reason: string | null;
  hr_email: string;
  created_at: string;
}

export type DecisionKind = "override" | "accept";

/** Superseded answer version kept for review history. */
export interface EarlierSubmission {
  id: string;
  kind: AnswerKind;
  text: string | null;
  audio: AudioMeta | null;
  submitted_at: string;
  superseded_at: string | null;
  decisions: DecisionView[];
}

/** The current answer inside CandidateReview.questions[].answer */
export interface AnswerReview {
  id: string;
  kind: AnswerKind;
  text: string | null;
  audio: AudioMeta | null;
  submitted_at: string;
  submission_count: number;
  job: JobView | null;
  final_score: number | null;
  final_source: "hr" | "suggested" | null;
  decisions: DecisionView[];
  earlier_submissions: EarlierSubmission[];
}

export interface QuestionRef {
  id: string;
  position: number;
  text: string;
  rubric: Record<string, string>;
}

export interface QuestionReview {
  question: QuestionRef;
  answer: AnswerReview | null;
}

/** GET /api/hr/candidates/{candidate_id} → 200 */
export interface CandidateReview {
  id: string;
  name: string;
  email: string;
  role: RoleRef;
  total_questions: number;
  answered_count: number;
  avg_suggested: number | null;
  avg_final: number | null;
  job_counts: JobCounts;
  questions: QuestionReview[];
}

/** GET /api/hr/jobs item — no score fields; read scores via CandidateReview. */
export interface JobListItem {
  id: number;
  status: JobStatus;
  attempts: number;
  last_error: string | null;
  needs_person_reason: string | null;
  updated_at: string;
  answer: { id: string; kind: AnswerKind; question_id: string };
  candidate: { id: string; name: string };
  role: RoleRef;
}

/** GET /api/hr/jobs → 200 */
export interface JobList {
  counts: JobCountsAll;
  jobs: JobListItem[];
}

/* ---------- HR actions ---------- */

/** POST /api/hr/answers/{answer_id}/override request body */
export interface OverrideRequest {
  score: number;
  reason: string;
}

/** POST /api/hr/answers/{answer_id}/accept request body */
export interface AcceptRequest {
  score: number;
}

/** POST /api/hr/jobs/{job_id}/retry request body — always empty. */
export type RetryRequest = Record<string, never>;
