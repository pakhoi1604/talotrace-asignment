// Typed API client. Mirrors docs/api-doc.md (the source of truth).
//
// URL rules:
// - Client components / browser code: call apiFetch with a relative "/api/..."
//   path — next.config.ts rewrites it to FastAPI, so requests stay same-origin.
// - Server components: a relative URL cannot be fetched server-side, so use
//   apiFetchServer, which targets API_URL directly.

import type { ApiError } from "@/lib/api-types";

export class ApiRequestError extends Error {
  constructor(
    public status: number,
    detail: string,
  ) {
    super(detail);
    this.name = "ApiRequestError";
  }
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = (await res.json()) as ApiError;
      if (body.detail) detail = body.detail;
    } catch {
      // Non-JSON error body — keep the status text.
    }
    throw new ApiRequestError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

/** Browser-side calls: same-origin /api path, proxied by the Next rewrite. */
export function apiFetch<T>(
  path: `/api/${string}`,
  init?: RequestInit,
): Promise<T> {
  return request<T>(path, init);
}

/** Server-side calls (server components, route handlers): absolute API URL. */
export function apiFetchServer<T>(
  path: `/api/${string}`,
  init?: RequestInit,
): Promise<T> {
  const base = process.env.API_URL ?? "http://localhost:8000";
  return request<T>(`${base}${path}`, init);
}
