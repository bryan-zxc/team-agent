"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import clsx from "clsx";
import { useWebSocket } from "@/hooks/useWebSocket";
import type { IDockviewPanelProps } from "dockview";
import type { Member, Message, Room, ToolApprovalBlock, WorkloadChat } from "@/types";
import { ToolApprovalCard } from "./ToolApprovalCard";
import styles from "./ChatTab.module.css";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type ChatTabParams = {
  roomId: string;
  room: Room;
  memberId: string | null;
  members: Member[];
};

function getMessageText(content: string): string {
  try {
    const data = JSON.parse(content);
    if (data?.blocks) {
      return data.blocks
        .filter((b: { type: string }) => b.type === "text")
        .map((b: { value: string }) => b.value)
        .join(" ");
    }
  } catch {
    /* legacy plain text */
  }
  return content;
}

function getToolApprovalBlock(content: string): ToolApprovalBlock | null {
  try {
    const data = JSON.parse(content);
    if (data?.blocks?.[0]?.type === "tool_approval_request") {
      return data.blocks[0] as ToolApprovalBlock;
    }
  } catch {
    /* not a tool approval */
  }
  return null;
}

/* ── ChatView: reusable messages + input for any chat ── */

type ChatViewProps = {
  chatId: string | null;
  memberId: string | null;
  members: Member[];
  placeholder: string;
  onAiMessage?: () => void;
};

function ChatView({ chatId, memberId, members, placeholder, onAiMessage }: ChatViewProps) {
  const [input, setInput] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const prevCountRef = useRef(0);

  const { messages, sendMessage, setMessages } = useWebSocket(chatId, memberId);

  useEffect(() => {
    if (!chatId) return;
    fetch(`${API_URL}/chats/${chatId}/messages`)
      .then((r) => r.json())
      .then((history: Message[]) => setMessages(history));
  }, [chatId, setMessages]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    if (messages.length > prevCountRef.current && onAiMessage) {
      const latest = messages[messages.length - 1];
      if (latest.type !== "human") {
        onAiMessage();
      }
    }
    prevCountRef.current = messages.length;
  }, [messages, onAiMessage]);

  const memberMap = useMemo(() => new Map(members.map((m) => [m.id, m])), [members]);

  const handleSend = useCallback(() => {
    if (!input.trim()) return;
    const text = input.trim();
    const mentions: string[] = [];
    const textLower = text.toLowerCase();
    for (const member of members) {
      if (textLower.includes(`@${member.display_name.toLowerCase()}`)) {
        mentions.push(member.id);
      }
    }
    sendMessage([{ type: "text", value: text }], mentions);
    setInput("");
  }, [input, members, sendMessage]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend],
  );

  const formatTime = (iso: string) => {
    const d = new Date(iso);
    return d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  };

  return (
    <div className={styles.chatView}>
      <div className={styles.messages}>
        {messages.map((msg) => {
          // Tool approval request — detect from content (type may be "ai" when loaded from API)
          const approvalBlock = getToolApprovalBlock(msg.content);
          if (approvalBlock) {
            return (
              <div key={msg.id} className={styles.approvalRow}>
                <ToolApprovalCard block={approvalBlock} />
              </div>
            );
          }

          const isSelf = msg.member_id === memberId;
          const isAi = msg.type !== "human";

          return (
            <div
              key={msg.id}
              className={clsx(styles.messageGroup, isSelf && styles.self, isAi && styles.ai)}
            >
              <div className={clsx(styles.msgAvatar, isAi ? styles.avatarAi : styles.avatarHuman)}>
                {msg.display_name[0]}
              </div>
              <div className={styles.msgBody}>
                <div className={styles.msgHeader}>
                  <span className={styles.msgAuthor}>{msg.display_name}</span>
                  {isAi && <span className={styles.aiBadge}>AI</span>}
                  <span className={styles.msgTime}>{formatTime(msg.created_at)}</span>
                </div>
                <div className={styles.msgBubble}>{getMessageText(msg.content)}</div>
              </div>
            </div>
          );
        })}
        <div ref={messagesEndRef} />
      </div>

      <div className={styles.inputArea}>
        <div className={styles.inputWrapper}>
          <textarea
            className={styles.inputField}
            placeholder={placeholder}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            rows={1}
          />
          <button className={styles.sendBtn} onClick={handleSend} aria-label="Send message">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <line x1="22" y1="2" x2="11" y2="13" />
              <polygon points="22 2 15 22 11 13 2 9 22 2" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
}

/* ── ChatTab: dockview panel with dynamic internal tabs ── */

export function ChatTab({ params }: IDockviewPanelProps<ChatTabParams>) {
  const { roomId, room, memberId, members } = params;
  const [workloads, setWorkloads] = useState<WorkloadChat[]>([]);
  const [activeChatId, setActiveChatId] = useState<string>(room.primary_chat_id);

  const refreshWorkloads = useCallback(() => {
    fetch(`${API_URL}/rooms/${roomId}/workloads`)
      .then((r) => r.json())
      .then((data: WorkloadChat[]) => setWorkloads(data))
      .catch(() => {});
  }, [roomId]);

  useEffect(() => {
    refreshWorkloads();
  }, [refreshWorkloads]);

  const hasWorkloads = workloads.length > 0;

  return (
    <div className={styles.container}>
      {hasWorkloads && (
        <div className={styles.tabs}>
          <button
            className={clsx(styles.tab, activeChatId === room.primary_chat_id && styles.tabActive)}
            onClick={() => setActiveChatId(room.primary_chat_id)}
          >
            Main
          </button>
          {workloads.map((w) => (
            <button
              key={w.id}
              className={clsx(styles.tab, activeChatId === w.id && styles.tabActive)}
              onClick={() => setActiveChatId(w.id)}
            >
              {w.owner_name}: {w.title}
            </button>
          ))}
        </div>
      )}

      <ChatView
        key={activeChatId}
        chatId={activeChatId}
        memberId={memberId}
        members={members}
        placeholder={`Message ${room.name}...`}
        onAiMessage={activeChatId === room.primary_chat_id ? refreshWorkloads : undefined}
      />
    </div>
  );
}
