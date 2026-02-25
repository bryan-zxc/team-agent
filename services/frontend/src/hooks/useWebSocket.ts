"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { API_URL } from "@/lib/api";
import type { Message } from "@/types";

const WS_URL = API_URL.replace(/^http/, "ws");

type ContentBlock =
  | { type: "text"; value: string }
  | { type: "mention"; member_id: string; display_name: string };

export function useWebSocket(
  chatId: string | null,
  memberId: string | null,
  onRoomEvent?: (event: Record<string, unknown>) => void,
) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout>>(undefined);
  const roomEventRef = useRef(onRoomEvent);
  roomEventRef.current = onRoomEvent;

  const connect = useCallback(() => {
    if (!chatId || !memberId) return;

    const ws = new WebSocket(`${WS_URL}/ws/${chatId}?member_id=${memberId}`);
    wsRef.current = ws;

    ws.onopen = () => setIsConnected(true);

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);

      // Room-level events (e.g. workload status) have an _event marker
      if (data._event) {
        roomEventRef.current?.(data);
        return;
      }

      const msg: Message = data;
      setMessages((prev) => {
        if (prev.some((m) => m.id === msg.id)) return prev;
        return [...prev, msg];
      });
    };

    ws.onclose = () => {
      setIsConnected(false);
      reconnectTimer.current = setTimeout(connect, 2000);
    };
  }, [chatId, memberId]);

  useEffect(() => {
    connect();
    return () => {
      clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
    };
  }, [connect]);

  const sendMessage = useCallback(
    (blocks: ContentBlock[], mentions: string[], replyToId?: string) => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(
          JSON.stringify({ blocks, mentions, reply_to_id: replyToId ?? null }),
        );
      }
    },
    [],
  );

  return { messages, sendMessage, isConnected, setMessages };
}
