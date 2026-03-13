"use client";

import { useEffect, useRef } from "react";
import { apiFetch } from "@/lib/api";

const INTERVAL_MS = 60_000;
const ACTIVE_WINDOW_MS = 60_000;

/**
 * Sends a heartbeat POST every 60 seconds while the user is active.
 * Activity is detected via mouse, keyboard, and scroll events.
 * If no activity occurred in the last 60 seconds, the heartbeat is skipped.
 */
export function useActivityHeartbeat(
  projectId: string,
  memberId: string | null,
): void {
  const lastActiveRef = useRef(0);

  useEffect(() => {
    if (!memberId) return;

    const markActive = () => {
      lastActiveRef.current = Date.now();
    };

    const events: (keyof DocumentEventMap)[] = [
      "mousemove",
      "mousedown",
      "keydown",
      "scroll",
      "pointerdown",
    ];

    for (const event of events) {
      document.addEventListener(event, markActive, { passive: true });
    }

    // Mark active immediately so the first interval tick can fire
    markActive();

    const interval = setInterval(() => {
      if (Date.now() - lastActiveRef.current < ACTIVE_WINDOW_MS) {
        apiFetch(
          `/projects/${projectId}/members/${memberId}/heartbeat`,
          { method: "POST" },
        ).catch(() => {});
      }
    }, INTERVAL_MS);

    return () => {
      for (const event of events) {
        document.removeEventListener(event, markActive);
      }
      clearInterval(interval);
    };
  }, [projectId, memberId]);
}
