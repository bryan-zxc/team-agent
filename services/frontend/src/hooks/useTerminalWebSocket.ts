"use client";

import { useCallback, useEffect, useRef } from "react";
import { API_URL } from "@/lib/api";

const WS_URL = API_URL.replace(/^http/, "ws");

type UseTerminalWebSocketOptions = {
  sessionId: string | null;
  onData: (data: Uint8Array) => void;
  onClosed: () => void;
};

export function useTerminalWebSocket({
  sessionId,
  onData,
  onClosed,
}: UseTerminalWebSocketOptions) {
  const wsRef = useRef<WebSocket | null>(null);
  const onDataRef = useRef(onData);
  onDataRef.current = onData;
  const onClosedRef = useRef(onClosed);
  onClosedRef.current = onClosed;

  const connect = useCallback(() => {
    if (!sessionId) return;

    const ws = new WebSocket(`${WS_URL}/ws/terminal/${sessionId}`);
    wsRef.current = ws;

    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);

      if (msg.type === "output") {
        const bytes = Uint8Array.from(atob(msg.data), (c) => c.charCodeAt(0));
        onDataRef.current(bytes);
      } else if (msg.type === "closed") {
        onClosedRef.current();
      }
    };

    ws.onclose = () => {
      // Terminal sessions are not auto-reconnected
    };
  }, [sessionId]);

  useEffect(() => {
    connect();
    return () => {
      wsRef.current?.close();
    };
  }, [connect]);

  const sendInput = useCallback((data: string) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      const b64 = btoa(data);
      wsRef.current.send(JSON.stringify({ type: "input", data: b64 }));
    }
  }, []);

  const sendResize = useCallback((cols: number, rows: number) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "resize", cols, rows }));
    }
  }, []);

  return { sendInput, sendResize };
}
