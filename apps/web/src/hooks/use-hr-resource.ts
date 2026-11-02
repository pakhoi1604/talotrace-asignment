"use client";

// One data hook for every HR screen: fetch on mount and when `deps` change,
// manual `reload()` for the Refresh button and post-action refetches.
// Manual only — no timers or polling (locked decision). A 401 redirects to
// sign-in; other errors become friendly copy via toHrMessage.

import { useCallback, useEffect, useRef, useState } from "react";

import { ApiRequestError } from "@/lib/api-client";
import { useHrUnauthorizedRedirect } from "@/lib/hr-auth-redirect";
import { toHrMessage } from "@/lib/hr-error-messages";

export interface HrResource<T> {
  data?: T;
  error?: string;
  /** HTTP status of the failure (e.g. 404 → not-found card), if the error was an API response. */
  status?: number;
  loading: boolean;
  refreshing: boolean;
  loadedAt?: Date;
  reload: () => Promise<void>;
}

export function useHrResource<T>(
  load: () => Promise<T>,
  deps: unknown[],
): HrResource<T> {
  const [data, setData] = useState<T>();
  const [error, setError] = useState<string>();
  const [status, setStatus] = useState<number>();
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [loadedAt, setLoadedAt] = useState<Date>();
  const onUnauthorized = useHrUnauthorizedRedirect();
  // Latest loader without making it an effect dep (callers pass inline lambdas).
  const loadRef = useRef(load);
  loadRef.current = load;
  const seq = useRef(0);

  const run = useCallback(
    async (initial: boolean) => {
      const ticket = ++seq.current;
      if (initial) setLoading(true);
      else setRefreshing(true);
      try {
        const result = await loadRef.current();
        if (ticket !== seq.current) return;
        setData(result);
        setError(undefined);
        setStatus(undefined);
        setLoadedAt(new Date());
      } catch (err) {
        if (ticket !== seq.current) return;
        if (!onUnauthorized(err)) {
          setError(toHrMessage(err));
          setStatus(err instanceof ApiRequestError ? err.status : undefined);
        }
      } finally {
        if (ticket === seq.current) {
          setLoading(false);
          setRefreshing(false);
        }
      }
      // eslint-disable-next-line react-hooks/exhaustive-deps -- caller declares deps
    },
    [onUnauthorized, ...deps],
  );

  useEffect(() => {
    void run(true);
  }, [run]);

  const reload = useCallback(() => run(false), [run]);

  return { data, error, status, loading, refreshing, loadedAt, reload };
}
