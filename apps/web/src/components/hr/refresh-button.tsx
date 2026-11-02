// Manual refresh: secondary button + "Updated HH:MM" timestamp.
// Deliberately no timers or polling — HR presses Refresh (locked decision).
// reload() keeps the old data visible while refetching (no full-page loader).

import { RotateCw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { formatTime } from "@/lib/format-time";

interface RefreshButtonProps {
  refreshing: boolean;
  loadedAt?: Date;
  onRefresh: () => void;
}

export function RefreshButton({
  refreshing,
  loadedAt,
  onRefresh,
}: RefreshButtonProps) {
  return (
    <div className="flex items-center gap-2.5">
      <Button
        variant="secondary"
        size="sm"
        onClick={onRefresh}
        disabled={refreshing}
      >
        <RotateCw
          className={refreshing ? "motion-safe:animate-spin" : undefined}
          aria-hidden
        />
        Refresh
      </Button>
      <span className="text-meta text-muted-foreground" aria-live="polite">
        {loadedAt
          ? `Updated ${formatTime(loadedAt.toISOString())}`
          : "Loading…"}
      </span>
    </div>
  );
}
