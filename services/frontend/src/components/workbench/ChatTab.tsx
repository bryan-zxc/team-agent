"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import clsx from "clsx";
import { useWebSocket } from "@/hooks/useWebSocket";
import type { IDockviewPanelProps } from "dockview";
import type { Member, Message, Room, ToolApprovalBlock, WorkloadChat, WorkloadStatusEvent } from "@/types";
import { ToolApprovalCard } from "./ToolApprovalCard";
import { WorkloadPanel } from "./WorkloadPanel";
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
  onRoomEvent?: (event: Record<string, unknown>) => void;
  workloadStatus?: string;
  workloadHasSession?: boolean;
  onInterrupt?: () => void;
};

function ChatView({
  chatId,
  memberId,
  members,
  placeholder,
  onAiMessage,
  onRoomEvent,
  workloadStatus,
  workloadHasSession,
  onInterrupt,
}: ChatViewProps) {
  const [input, setInput] = useState("");
  const [resuming, setResuming] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const prevCountRef = useRef(0);
  const prevStatusRef = useRef(workloadStatus);

  const { messages, sendMessage, setMessages } = useWebSocket(chatId, memberId, onRoomEvent);

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

  // Clear resuming state when workload transitions to running
  useEffect(() => {
    if (prevStatusRef.current !== "running" && workloadStatus === "running") {
      setResuming(false);
    }
    prevStatusRef.current = workloadStatus;
  }, [workloadStatus]);

  const memberMap = useMemo(() => new Map(members.map((m) => [m.id, m])), [members]);

  const isPaused = workloadStatus === "needs_attention" || workloadStatus === "completed";

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
    if (isPaused && workloadHasSession) {
      setResuming(true);
    }
  }, [input, members, sendMessage, isPaused, workloadHasSession]);

  const isRunning = workloadStatus === "running" || workloadStatus === "assigned";

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
      if (e.key === "Escape" && isRunning && onInterrupt) {
        e.preventDefault();
        if (input.trim()) {
          setInput("");
        } else {
          onInterrupt();
        }
      }
    },
    [handleSend, isRunning, onInterrupt, input],
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
                <ToolApprovalCard block={approvalBlock} disabled={!!workloadStatus && !isRunning} />
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

      {workloadStatus && !isRunning && (
        <div className={styles.statusBanner}>
          {resuming ? (
            <>
              <span className={styles.statusDot} />
              <span>Resuming session...</span>
            </>
          ) : isPaused && workloadHasSession ? (
            <span>Agent paused — send a message to resume</span>
          ) : isPaused && !workloadHasSession ? (
            <span>Agent session ended</span>
          ) : null}
        </div>
      )}

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
          {isRunning && onInterrupt && (
            <button
              className={styles.interruptBtn}
              onClick={onInterrupt}
              aria-label="Interrupt workload"
              title="Interrupt (Esc)"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <rect x="6" y="6" width="12" height="12" rx="2" />
              </svg>
            </button>
          )}
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
  const [panelOpen, setPanelOpen] = useState(false);

  const refreshWorkloads = useCallback(() => {
    fetch(`${API_URL}/rooms/${roomId}/workloads`)
      .then((r) => r.json())
      .then((data: WorkloadChat[]) => setWorkloads(data))
      .catch(() => {});
  }, [roomId]);

  useEffect(() => {
    refreshWorkloads();
  }, [refreshWorkloads]);

  const handleRoomEvent = useCallback(
    (event: Record<string, unknown>) => {
      if (event._event === "workload_status") {
        const e = event as unknown as WorkloadStatusEvent;
        setWorkloads((prev) => {
          const idx = prev.findIndex((w) => w.workload_id === e.workload_id);
          if (idx === -1) {
            // New workload — re-fetch to get full data
            refreshWorkloads();
            return prev;
          }
          const updated = [...prev];
          updated[idx] = { ...updated[idx], status: e.status, updated_at: e.updated_at };
          return updated;
        });
      }
    },
    [refreshWorkloads],
  );

  const handleCancel = useCallback(
    async (workloadId: string) => {
      // Optimistic update
      setWorkloads((prev) =>
        prev.map((w) =>
          w.workload_id === workloadId
            ? { ...w, status: "cancelled", updated_at: new Date().toISOString() }
            : w,
        ),
      );
      try {
        const resp = await fetch(`${API_URL}/workloads/${workloadId}/cancel`, {
          method: "POST",
        });
        if (!resp.ok) refreshWorkloads();
      } catch {
        refreshWorkloads();
      }
    },
    [refreshWorkloads],
  );

  const handleComplete = useCallback(
    async (workloadId: string) => {
      // Optimistic update
      setWorkloads((prev) =>
        prev.map((w) =>
          w.workload_id === workloadId
            ? { ...w, status: "completed", updated_at: new Date().toISOString() }
            : w,
        ),
      );
      try {
        const resp = await fetch(`${API_URL}/workloads/${workloadId}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ status: "completed" }),
        });
        if (!resp.ok) refreshWorkloads();
      } catch {
        refreshWorkloads();
      }
    },
    [refreshWorkloads],
  );

  const handleInterrupt = useCallback(
    async (workloadId: string) => {
      setWorkloads((prev) =>
        prev.map((w) =>
          w.workload_id === workloadId
            ? { ...w, status: "needs_attention", updated_at: new Date().toISOString() }
            : w,
        ),
      );
      try {
        const resp = await fetch(`${API_URL}/workloads/${workloadId}/interrupt`, {
          method: "POST",
        });
        if (!resp.ok) refreshWorkloads();
      } catch {
        refreshWorkloads();
      }
    },
    [refreshWorkloads],
  );

  // Find workload for the active chat (if viewing a workload chat)
  const activeWorkload = workloads.find((w) => w.id === activeChatId);

  const hasWorkloads = workloads.length > 0;

  return (
    <div className={styles.container}>
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
        <button
          className={clsx(styles.panelToggle, panelOpen && styles.panelToggleActive)}
          onClick={() => setPanelOpen((p) => !p)}
          aria-label="Toggle workload panel"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
            <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
            <line x1="15" y1="3" x2="15" y2="21" />
          </svg>
        </button>
      </div>

      <div className={styles.body}>
        <ChatView
          key={activeChatId}
          chatId={activeChatId}
          memberId={memberId}
          members={members}
          placeholder={`Message ${room.name}...`}
          onAiMessage={activeChatId === room.primary_chat_id ? refreshWorkloads : undefined}
          onRoomEvent={handleRoomEvent}
          workloadStatus={activeWorkload?.status}
          workloadHasSession={activeWorkload?.has_session}
          onInterrupt={
            activeWorkload
              ? () => handleInterrupt(activeWorkload.workload_id)
              : undefined
          }
        />
        <div className={clsx(styles.panel, !panelOpen && styles.panelCollapsed)}>
          {panelOpen && (
            <WorkloadPanel
              workloads={workloads}
              activeChatId={activeChatId}
              onSelectWorkload={setActiveChatId}
              onCancel={handleCancel}
              onComplete={handleComplete}
              onInterrupt={handleInterrupt}
            />
          )}
        </div>
      </div>
    </div>
  );
}
