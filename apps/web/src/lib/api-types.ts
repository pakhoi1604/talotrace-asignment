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
