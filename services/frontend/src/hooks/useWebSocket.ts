"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { Message } from "@/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const WS_URL = API_URL.replace(/^http/, "ws");

type ContentBlock = { type: "text"; value: string };

export function useWebSocket(chatId: string | null, memberId: string | null) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout>>();

  const connect = useCallback(() => {
    if (!chatId || !memberId) return;

    const ws = new WebSocket(`${WS_URL}/ws/${chatId}?member_id=${memberId}`);
    wsRef.current = ws;

    ws.onopen = () => setIsConnected(true);

    ws.onmessage = (event) => {
      const msg: Message = JSON.parse(event.data);
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
    (blocks: ContentBlock[], mentions: string[]) => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ blocks, mentions }));
      }
    },
    [],
  );

  return { messages, sendMessage, isConnected, setMessages };
}
