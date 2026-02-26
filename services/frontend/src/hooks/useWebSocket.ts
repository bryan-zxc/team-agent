"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { API_URL } from "@/lib/api";
import type { AgentActivityEvent, Message } from "@/types";

const WS_URL = API_URL.replace(/^http/, "ws");

type ContentBlock =
  | { type: "text"; value: string }
  | { type: "mention"; member_id: string; display_name: string };

export type TypingEvent = { member_id: string; display_name: string };

export function useWebSocket(
  chatId: string | null,
  memberId: string | null,
  onRoomEvent?: (event: Record<string, unknown>) => void,
  onTypingEvent?: (event: TypingEvent) => void,
  onAgentActivity?: (event: AgentActivityEvent) => void,
) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout>>(undefined);
  const roomEventRef = useRef(onRoomEvent);
  roomEventRef.current = onRoomEvent;
  const typingEventRef = useRef(onTypingEvent);
  typingEventRef.current = onTypingEvent;
  const agentActivityRef = useRef(onAgentActivity);
  agentActivityRef.current = onAgentActivity;

  const connect = useCallback(() => {
    if (!chatId || !memberId) return;

    const ws = new WebSocket(`${WS_URL}/ws/${chatId}?member_id=${memberId}`);
    wsRef.current = ws;

    ws.onopen = () => setIsConnected(true);

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);

      // Typing events — ephemeral, handled separately
      if (data._event === "typing") {
        typingEventRef.current?.(data as TypingEvent);
        return;
      }

      // Agent activity events — streaming status heartbeat
      if (data._event === "agent_activity") {
        agentActivityRef.current?.(data as AgentActivityEvent);
        return;
      }

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

  const sendTyping = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ _event: "typing" }));
    }
  }, []);

  return { messages, sendMessage, sendTyping, isConnected, setMessages };
}
