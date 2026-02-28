"use client";

import { useCallback, useEffect, useRef } from "react";
import { API_URL } from "@/lib/api";

const WS_URL = API_URL.replace(/^http/, "ws");

type UseScreencastWebSocketOptions = {
  workloadId: string | null;
  onFrame: (data: string) => void;
  onStopped: () => void;
};

export function useScreencastWebSocket({
  workloadId,
  onFrame,
  onStopped,
}: UseScreencastWebSocketOptions) {
  const wsRef = useRef<WebSocket | null>(null);
  const onFrameRef = useRef(onFrame);
  onFrameRef.current = onFrame;
  const onStoppedRef = useRef(onStopped);
  onStoppedRef.current = onStopped;

  const connect = useCallback(() => {
    if (!workloadId) return;

    const ws = new WebSocket(`${WS_URL}/ws/screencast/${workloadId}`);
    wsRef.current = ws;

    let wasConnected = false;
    let receivedStopped = false;

    ws.onopen = () => {
      wasConnected = true;
    };

    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);

      if (msg.type === "frame") {
        onFrameRef.current(msg.data);
      } else if (msg.type === "stopped") {
        receivedStopped = true;
        onStoppedRef.current();
      }
    };

    ws.onclose = () => {
      // Only treat as "stopped" if the WS was actually connected.
      // Ignore close events from WebSockets that never established
      // (e.g. React StrictMode cleanup during double-render).
      if (!receivedStopped && wasConnected) {
        onStoppedRef.current();
      }
    };
  }, [workloadId]);

  useEffect(() => {
    connect();
    return () => {
      wsRef.current?.close();
    };
  }, [connect]);
}
