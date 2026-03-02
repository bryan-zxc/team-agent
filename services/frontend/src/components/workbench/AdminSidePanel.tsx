"use client";

import { useState } from "react";
import clsx from "clsx";
import type { AdminChat, Member } from "@/types";
import styles from "./AdminSidePanel.module.css";

type AdminSidePanelProps = {
  adminChats: AdminChat[];
  onChatClick: (chatId: string) => void;
  currentMember?: Member | null;
};

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

const ACTIVE_STATUSES = new Set(["running", "needs_attention"]);

export function AdminSidePanel({ adminChats, onChatClick, currentMember }: AdminSidePanelProps) {
  const [historyOpen, setHistoryOpen] = useState(true);

  const currentChat = adminChats.find((c) => ACTIVE_STATUSES.has(c.status)) ?? null;
  const historyChats = adminChats
    .filter((c) => !ACTIVE_STATUSES.has(c.status))
    .sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime());

  return (
    <div className={styles.panel}>
      <div className={styles.header}>
        <div className={styles.logo}>
          <div className={styles.logoMark}>ta</div>
          <span className={styles.logoText}>Team Agent</span>
        </div>
      </div>

      <div className={styles.sectionHeader}>
        <span className={styles.sectionLabel}>Sessions</span>
      </div>

      <div className={styles.historySection}>
        {currentChat && (
          <>
            <div className={styles.currentLabel}>Current</div>
            <div className={styles.historyList}>
              <button
                className={styles.chatItem}
                onClick={() => onChatClick(currentChat.id)}
              >
                <div className={styles.chatTitle}>
                  {currentChat.title || "Untitled session"}
                </div>
                <div className={styles.chatMeta}>
                  <span>{timeAgo(currentChat.updated_at)}</span>
                  {currentChat.owner_name && <span>· {currentChat.owner_name}</span>}
                </div>
              </button>
            </div>
          </>
        )}

        <button
          className={styles.historyToggle}
          onClick={() => setHistoryOpen((p) => !p)}
        >
          <span className={clsx(styles.chevron, historyOpen && styles.chevronOpen)}>&#x25B6;</span>
          <span className={styles.historyLabel}>History</span>
          {historyChats.length > 0 && (
            <span className={styles.historyCount}>{historyChats.length}</span>
          )}
        </button>

        {historyOpen && (
          <div className={styles.historyList}>
            {historyChats.length === 0 && (
              <div className={styles.emptyState}>No sessions yet</div>
            )}
            {historyChats.map((chat) => {
              const isCancelled = chat.status === "cancelled";
              return (
                <button
                  key={chat.id}
                  className={styles.chatItem}
                  onClick={() => onChatClick(chat.id)}
                >
                  <div className={clsx(styles.chatTitle, isCancelled && styles.chatTitleCancelled)}>
                    {chat.title || "Untitled session"}
                  </div>
                  <div className={styles.chatMeta}>
                    <span>{timeAgo(chat.updated_at)}</span>
                    {chat.owner_name && <span>· {chat.owner_name}</span>}
                  </div>
                </button>
              );
            })}
          </div>
        )}
      </div>

      {currentMember && (
        <div className={styles.footer}>
          <div className={styles.userDisplay}>
            <div className={styles.avatar}>
              {currentMember.display_name[0]}
            </div>
            <div className={styles.userInfo}>
              <div className={styles.userName}>{currentMember.display_name}</div>
              <div className={styles.userRole}>{currentMember.type}</div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
