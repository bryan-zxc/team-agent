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

    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);

      if (msg.type === "frame") {
        onFrameRef.current(msg.data);
      } else if (msg.type === "stopped") {
        onStoppedRef.current();
      }
    };

    ws.onclose = () => {
      // Screencast sessions are not auto-reconnected
    };
  }, [workloadId]);

  useEffect(() => {
    connect();
    return () => {
      wsRef.current?.close();
    };
  }, [connect]);
}
