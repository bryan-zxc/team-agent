"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import clsx from "clsx";
import { useWebSocket } from "@/hooks/useWebSocket";
import { Sidebar } from "@/components/sidebar/Sidebar";
import { AddMemberModal } from "@/components/members/AddMemberModal";
import type { Member, Message, Room, User } from "@/types";
import styles from "./page.module.css";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function ChatPage() {
  const params = useParams<{ roomId: string }>();
  const router = useRouter();

  const [room, setRoom] = useState<Room | null>(null);
  const [rooms, setRooms] = useState<Room[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [members, setMembers] = useState<Member[]>([]);
  const [memberId, setMemberId] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [showAddModal, setShowAddModal] = useState(false);
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
    fetch(`${API_URL}/members`).then((r) => r.json()).then(setMembers);
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
      <Sidebar
        rooms={rooms}
        members={members}
        activeRoomId={params.roomId}
        onRoomClick={(roomId) => router.push(`/chat/${roomId}`)}
        onAddMember={() => setShowAddModal(true)}
      >
        {currentUser && (
          <div className={styles.sidebarFooter}>
            <div className={styles.userDisplay}>
              <div className={clsx(styles.avatar, styles.avatarHuman)}>
                {currentUser.display_name[0]}
              </div>
              <div className={styles.userInfo}>
                <div className={styles.userName}>{currentUser.display_name}</div>
                <div className={styles.userRole}>{currentUser.type}</div>
              </div>
            </div>
          </div>
        )}
      </Sidebar>

      <main className={styles.main}>
        <header className={styles.chatHeader}>
          <h2 className={styles.chatTitle}>{room?.name ?? "Loading..."}</h2>
        </header>

        <div className={styles.messages}>
          {messages.map((msg) => {
            const author = userMap.get(msg.member_id);
            const isSelf = msg.member_id === memberId;
            const isAi = author?.type === "ai";

            return (
              <div
                key={msg.id}
                className={clsx(styles.messageGroup, isSelf && styles.self, isAi && styles.ai)}
              >
                <div
                  className={clsx(styles.msgAvatar, isAi ? styles.avatarAi : styles.avatarHuman)}
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
            <button className={styles.sendBtn} onClick={handleSend} aria-label="Send message">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <line x1="22" y1="2" x2="11" y2="13" />
                <polygon points="22 2 15 22 11 13 2 9 22 2" />
              </svg>
            </button>
          </div>
        </div>
      </main>

      <AddMemberModal
        open={showAddModal}
        onClose={() => setShowAddModal(false)}
        onMemberAdded={(member) => setMembers((prev) => [...prev, member])}
      />
    </div>
  );
}
