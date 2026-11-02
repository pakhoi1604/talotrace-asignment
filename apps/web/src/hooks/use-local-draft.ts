"use client";

import { useCallback, useEffect, useRef, useState } from "react";

const DEBOUNCE_MS = 300;

function writeDraft(key: string, value: string) {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    // Private mode / quota: the draft just stays in memory.
  }
}

/**
 * Per-candidate, per-question answer draft in localStorage.
 * The key uses a token suffix (shared-device scoping) — the full token is
 * never written to storage. `initial` (e.g. a just-submitted answer) is used
 * when no stored draft exists.
 */
export function useLocalDraft(token: string, questionId: string, initial = "") {
  const key = `talotrace:draft:${token.slice(-8)}:${questionId}`;
  const [text, setTextState] = useState(initial);
  const timer = useRef<number | undefined>(undefined);
  const pending = useRef<{ key: string; value: string } | null>(null);

  // Load the stored draft whenever the question (or prefill) changes.
  useEffect(() => {
    let saved: string | null = null;
    try {
      saved = window.localStorage.getItem(key);
    } catch {
      // Private mode: nothing stored.
    }
    setTextState(saved ?? initial);
  }, [key, initial]);

  const setText = useCallback(
    (value: string) => {
      setTextState(value);
      pending.current = { key, value };
      window.clearTimeout(timer.current);
      timer.current = window.setTimeout(() => {
        if (pending.current) {
          writeDraft(pending.current.key, pending.current.value);
          pending.current = null;
        }
      }, DEBOUNCE_MS);
    },
    [key],
  );

  const clear = useCallback(() => {
    window.clearTimeout(timer.current);
    pending.current = null;
    try {
      window.localStorage.removeItem(key);
    } catch {
      // Private mode.
    }
  }, [key]);

  // Flush a pending debounced write on unmount.
  useEffect(
    () => () => {
      window.clearTimeout(timer.current);
      if (pending.current)
        writeDraft(pending.current.key, pending.current.value);
    },
    [],
  );

  return { text, setText, clear };
}
