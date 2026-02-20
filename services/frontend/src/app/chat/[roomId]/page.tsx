"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useTheme } from "@/hooks/useTheme";
import { useWebSocket } from "@/hooks/useWebSocket";
import type { Message, Room, User } from "@/types";
import styles from "./page.module.css";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function ChatPage() {
  const params = useParams<{ roomId: string }>();
  const router = useRouter();
  const { theme, toggle } = useTheme();

  const [room, setRoom] = useState<Room | null>(null);
  const [rooms, setRooms] = useState<Room[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [memberId, setMemberId] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const chatId = room?.primary_chat_id ?? null;
  const { messages, sendMessage, setMessages } = useWebSocket(chatId, memberId);

  // Load user from localStorage
  useEffect(() => {
    const stored = localStorage.getItem("member_id");
    if (!stored) {
      router.push("/");
      return;
    }
    setMemberId(stored);
  }, [router]);

  // Fetch rooms, users, and message history
  useEffect(() => {
    fetch(`${API_URL}/rooms`).then((r) => r.json()).then((data: Room[]) => {
      setRooms(data);
      const current = data.find((r: Room) => r.id === params.roomId);
      if (current) setRoom(current);
    });
    fetch(`${API_URL}/users`).then((r) => r.json()).then(setUsers);
  }, [params.roomId]);

  useEffect(() => {
    if (!params.roomId) return;
    fetch(`${API_URL}/rooms/${params.roomId}/messages`)
      .then((r) => r.json())
      .then((history: Message[]) => setMessages(history));
  }, [params.roomId, setMessages]);

  // Auto-scroll on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const userMap = new Map(users.map((u) => [u.id, u]));
  const currentUser = memberId ? userMap.get(memberId) : null;

  const handleSend = useCallback(() => {
    if (!input.trim()) return;
    sendMessage(input.trim());
    setInput("");
  }, [input, sendMessage]);

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
    <div className={styles.layout}>
      {/* Sidebar */}
      <aside className={styles.sidebar}>
        <div className={styles.sidebarHeader}>
          <div className={styles.logo}>
            <div className={styles.logoMark}>ta</div>
            <h1 className={styles.logoText}>Team Agent</h1>
          </div>
          <button className={styles.themeToggle} onClick={toggle} title="Toggle theme">
            {theme === "light" ? "\u263D" : "\u2600"}
          </button>
        </div>

        <div className={styles.sectionLabel}>Rooms</div>

        <div className={styles.roomList}>
          {rooms.map((r) => (
            <button
              key={r.id}
              className={`${styles.roomItem} ${r.id === params.roomId ? styles.roomItemActive : ""}`}
              onClick={() => router.push(`/chat/${r.id}`)}
            >
              <div className={`${styles.roomIcon} ${r.id === params.roomId ? styles.roomIconActive : ""}`}>
                #
              </div>
              <div className={styles.roomInfo}>
                <div className={styles.roomName}>{r.name}</div>
              </div>
            </button>
          ))}
        </div>

        <div className={styles.sidebarFooter}>
          {currentUser && (
            <div className={styles.userDisplay}>
              <div className={`${styles.avatar} ${styles.avatarHuman}`}>
                {currentUser.display_name[0]}
              </div>
              <div className={styles.userInfo}>
                <div className={styles.userName}>{currentUser.display_name}</div>
                <div className={styles.userRole}>{currentUser.type}</div>
              </div>
            </div>
          )}
        </div>
      </aside>

      {/* Chat */}
      <main className={styles.main}>
        <div className={styles.chatHeader}>
          <h2 className={styles.chatTitle}>{room?.name ?? "Loading..."}</h2>
        </div>

        <div className={styles.messages}>
          {messages.map((msg) => {
            const author = userMap.get(msg.member_id);
            const isSelf = msg.member_id === memberId;
            const isAi = author?.type === "ai";

            return (
              <div
                key={msg.id}
                className={`${styles.messageGroup} ${isSelf ? styles.self : ""} ${isAi ? styles.ai : ""}`}
              >
                <div
                  className={`${styles.msgAvatar} ${isAi ? styles.avatarAi : styles.avatarHuman}`}
                >
                  {msg.display_name[0]}
                </div>
                <div className={styles.msgBody}>
                  <div className={styles.msgHeader}>
                    <span className={styles.msgAuthor}>{msg.display_name}</span>
                    {isAi && <span className={styles.aiBadge}>AI</span>}
                    <span className={styles.msgTime}>{formatTime(msg.created_at)}</span>
                  </div>
                  <div className={styles.msgBubble}>{msg.content}</div>
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
              placeholder={`Message ${room?.name ?? ""}...`}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              rows={1}
            />
            <button className={styles.sendBtn} onClick={handleSend}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <line x1="22" y1="2" x2="11" y2="13" />
                <polygon points="22 2 15 22 11 13 2 9 22 2" />
              </svg>
            </button>
          </div>
        </div>
      </main>
    </div>
  );
}
