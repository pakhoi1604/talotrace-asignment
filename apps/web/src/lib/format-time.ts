/** Local "HH:MM" display for API timestamps (e.g. "received at 10:14"). */
export function formatTime(iso: string): string {
  return new Intl.DateTimeFormat(undefined, {
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(iso));
}
