"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import clsx from "clsx";
import { useWebSocket } from "@/hooks/useWebSocket";
import type { IDockviewPanelProps } from "dockview";
import type { Member, Message, Room } from "@/types";
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

type InternalTab = "chat" | "workloads";

export function ChatTab({ params }: IDockviewPanelProps<ChatTabParams>) {
  const { roomId, room, memberId, members } = params;
  const [activeTab, setActiveTab] = useState<InternalTab>("chat");
  const [input, setInput] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const chatId = room.primary_chat_id;
  const { messages, sendMessage, setMessages } = useWebSocket(chatId, memberId);

  useEffect(() => {
    fetch(`${API_URL}/rooms/${roomId}/messages`)
      .then((r) => r.json())
      .then((history: Message[]) => setMessages(history));
  }, [roomId, setMessages]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const memberMap = new Map(members.map((m) => [m.id, m]));

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
    <div className={styles.container}>
      <div className={styles.tabs}>
        <button
          className={clsx(styles.tab, activeTab === "chat" && styles.tabActive)}
          onClick={() => setActiveTab("chat")}
        >
          Chat
        </button>
        <button
          className={clsx(styles.tab, activeTab === "workloads" && styles.tabActive)}
          onClick={() => setActiveTab("workloads")}
        >
          Workloads
        </button>
      </div>

      {activeTab === "chat" ? (
        <div className={styles.chatView}>
          <div className={styles.messages}>
            {messages.map((msg) => {
              const author = memberMap.get(msg.member_id);
              const isSelf = msg.member_id === memberId;
              const isAi = msg.type === "ai" || author?.type === "ai";

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
                placeholder={`Message ${room.name}...`}
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
      ) : (
        <div className={styles.workloadsView}>
          <div className={styles.workloadsPlaceholder}>
            <p className={styles.placeholderText}>Workloads will appear here</p>
          </div>
        </div>
      )}
    </div>
  );
}
