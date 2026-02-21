"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import clsx from "clsx";
import { useWebSocket } from "@/hooks/useWebSocket";
import { Sidebar } from "@/components/sidebar/Sidebar";
import { AddMemberModal } from "@/components/members/AddMemberModal";
import type { Member, Message, Room } from "@/types";
import styles from "./page.module.css";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/** Extract display text from structured or legacy content. */
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

export default function ChatPage() {
  const params = useParams<{ projectId: string; roomId: string }>();
  const router = useRouter();

  const [room, setRoom] = useState<Room | null>(null);
  const [rooms, setRooms] = useState<Room[]>([]);
  const [members, setMembers] = useState<Member[]>([]);
  const [memberId, setMemberId] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [showAddModal, setShowAddModal] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const chatId = room?.primary_chat_id ?? null;
  const { messages, sendMessage, setMessages } = useWebSocket(chatId, memberId);

  // Derive member_id from global user_id
  useEffect(() => {
    const userId = localStorage.getItem("user_id");
    if (!userId) {
      router.push("/");
      return;
    }
    // Wait for members to load, then derive
    if (members.length > 0) {
      const match = members.find((m) => m.user_id === userId);
      if (match) setMemberId(match.id);
    }
  }, [members, router]);

  // Fetch rooms and members for this project
  useEffect(() => {
    if (!params.projectId) return;
    fetch(`${API_URL}/projects/${params.projectId}/rooms`)
      .then((r) => r.json())
      .then((data: Room[]) => {
        setRooms(data);
        const current = data.find((r: Room) => r.id === params.roomId);
        if (current) setRoom(current);
      });
    fetch(`${API_URL}/projects/${params.projectId}/members`)
      .then((r) => r.json())
      .then(setMembers);
  }, [params.projectId, params.roomId]);

  // Load message history
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

  const memberMap = new Map(members.map((m) => [m.id, m]));
  const currentMember = memberId ? memberMap.get(memberId) : null;

  const handleSend = useCallback(() => {
    if (!input.trim()) return;

    const text = input.trim();

    // Build mentions by matching @name against members list
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
    <div className={styles.layout}>
      <Sidebar
        rooms={rooms}
        members={members}
        activeRoomId={params.roomId}
        onRoomClick={(roomId) => router.push(`/project/${params.projectId}/chat/${roomId}`)}
        onCreateRoom={async (name) => {
          const res = await fetch(`${API_URL}/projects/${params.projectId}/rooms`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name }),
          });
          const newRoom: Room = await res.json();
          setRooms((prev) => [...prev, newRoom]);
        }}
        onRenameRoom={async (roomId, newName) => {
          const res = await fetch(`${API_URL}/projects/${params.projectId}/rooms/${roomId}`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name: newName }),
          });
          const updated: Room = await res.json();
          setRooms((prev) => prev.map((r) => (r.id === updated.id ? updated : r)));
          if (updated.id === params.roomId) setRoom(updated);
        }}
        onAddMember={() => setShowAddModal(true)}
        onMemberClick={(id) => router.push(`/project/${params.projectId}/members/${id}`)}
      >
        {currentMember && (
          <div className={styles.sidebarFooter}>
            <div className={styles.userDisplay}>
              <div className={clsx(styles.avatar, styles.avatarHuman)}>
                {currentMember.display_name[0]}
              </div>
              <div className={styles.userInfo}>
                <div className={styles.userName}>{currentMember.display_name}</div>
                <div className={styles.userRole}>{currentMember.type}</div>
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
            const author = memberMap.get(msg.member_id);
            const isSelf = msg.member_id === memberId;
            const isAi = msg.type === "ai" || author?.type === "ai";

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
        projectId={params.projectId}
        onClose={() => setShowAddModal(false)}
        onMemberAdded={(member) => setMembers((prev) => [...prev, member])}
      />
    </div>
  );
}
