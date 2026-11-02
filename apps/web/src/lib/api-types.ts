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
