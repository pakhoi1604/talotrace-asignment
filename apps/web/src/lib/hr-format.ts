// Display helpers for the HR area. `formatTime` is shared with the candidate
// area — import it, don't redefine it.

import type { JobStatus } from "@/lib/api-types";

export { formatTime } from "@/lib/format-time";

/** "2 Nov, 09:41" for decision/attempt timestamps. */
export function formatDateTime(iso: string): string {
  return new Intl.DateTimeFormat(undefined, {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(iso));
}

/** Short recency for "last activity" columns: just now · 12 min ago · 3 h ago · Yesterday · date. */
export function formatRelative(iso: string, now: Date = new Date()): string {
  const diff = now.getTime() - new Date(iso).getTime();
  const minutes = Math.floor(diff / 60_000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} h ago`;
  if (hours < 48) return "Yesterday";
  return new Intl.DateTimeFormat(undefined, {
    day: "numeric",
    month: "short",
  }).format(new Date(iso));
}

/** "3.2" or an em dash when there is nothing to average. */
export function formatAvg(n: number | null): string {
  return n === null ? "—" : n.toFixed(1);
}

/** "1.4 MB" for audio meta lines. */
export function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  const kb = n / 1024;
  if (kb < 1024) return `${kb.toFixed(1).replace(/\.0$/, "")} KB`;
  return `${(kb / 1024).toFixed(1).replace(/\.0$/, "")} MB`;
}

const AUDIO_FORMATS: Record<string, string> = {
  "audio/mp4": "M4A",
  "audio/mpeg": "MP3",
  "audio/wav": "WAV",
  "audio/webm": "WEBM",
  "audio/ogg": "OGG",
};

/** "M4A", "MP3"… from the API's extension-derived content type. */
export function audioFormatLabel(contentType: string | null): string {
  if (!contentType) return "audio";
  return (
    AUDIO_FORMATS[contentType] ??
    contentType.split("/")[1]?.toUpperCase() ??
    "audio"
  );
}

/** "Linh Tran" → "LT". */
export function initials(name: string): string {
  const parts = name.trim().split(/\s+/);
  return (
    (parts[0]?.[0] ?? "") + (parts.length > 1 ? parts[parts.length - 1][0] : "")
  ).toUpperCase();
}

/** The UI shows `running` jobs as "Queued" (the brief's four statuses). */
export function displayStatus(status: JobStatus): JobStatus {
  return status === "running" ? "queued" : status;
}
