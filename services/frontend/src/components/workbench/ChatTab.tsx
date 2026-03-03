"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import clsx from "clsx";
import type { IDockviewPanelProps } from "dockview";
import type { Member, Room, WorkloadChat, WorkloadStatusEvent } from "@/types";
import { apiFetch } from "@/lib/api";
import { ChatView } from "./ChatView";
import { WorkloadPanel } from "./WorkloadPanel";
import styles from "./ChatTab.module.css";

type ChatTabParams = {
  roomId: string;
  room: Room;
  memberId: string | null;
  members: Member[];
  projectId: string;
  onScreencastStarted?: (chatId: string, title: string) => void;
  onNavigateAdmin?: (chatId?: string) => void;
  onAttentionChange?: (roomId: string, needsAttention: boolean) => void;
};

export function ChatTab({ params }: IDockviewPanelProps<ChatTabParams>) {
  const { roomId, room, memberId, members, projectId, onScreencastStarted, onNavigateAdmin, onAttentionChange } = params;
  const [workloads, setWorkloads] = useState<WorkloadChat[]>([]);
  const [activeChatId, setActiveChatId] = useState<string>(room.primary_chat_id);
  const [panelOpen, setPanelOpen] = useState(false);
  const [hiddenTabs, setHiddenTabs] = useState<Set<string>>(new Set());

  const refreshWorkloads = useCallback(() => {
    apiFetch(`/rooms/${roomId}/workloads`)
      .then((r) => r.json())
      .then((data: WorkloadChat[]) => setWorkloads(data))
      .catch(() => {});
  }, [roomId]);

  useEffect(() => {
    refreshWorkloads();
  }, [refreshWorkloads]);

  // Report to Workbench when any workload in this room needs attention
  useEffect(() => {
    const needsAttention = workloads.some((w) => w.status === "needs_attention" || w.status === "awaiting_approval");
    onAttentionChange?.(roomId, needsAttention);
  }, [workloads, roomId, onAttentionChange]);

  const handleRoomEvent = useCallback(
    (event: Record<string, unknown>) => {
      if (event._event === "workload_status" && event.screencast_started) {
        const cid = event.chat_id as string;
        const name = event.owner_name as string | undefined;
        const title = name ? `Live View — ${name}` : "Live View";
        onScreencastStarted?.(cid, title);
        return;
      }
      if (event._event === "workload_status") {
        const e = event as unknown as WorkloadStatusEvent;
        setWorkloads((prev) => {
          const idx = prev.findIndex((w) => w.id === e.chat_id);
          if (idx === -1) {
            // New workload — re-fetch to get full data
            refreshWorkloads();
            return prev;
          }
          const updated = [...prev];
          updated[idx] = {
            ...updated[idx],
            status: e.status,
            updated_at: e.updated_at,
            ...(e.permission_mode ? { permission_mode: e.permission_mode } : {}),
          };
          return updated;
        });
      }
    },
    [refreshWorkloads, onScreencastStarted],
  );

  const handleCancel = useCallback(
    async (chatId: string) => {
      // Optimistic update
      setWorkloads((prev) =>
        prev.map((w) =>
          w.id === chatId
            ? { ...w, status: "cancelled", updated_at: new Date().toISOString() }
            : w,
        ),
      );
      try {
        const resp = await apiFetch(`/chats/${chatId}/cancel`, {
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
    async (chatId: string) => {
      // Optimistic update
      setWorkloads((prev) =>
        prev.map((w) =>
          w.id === chatId
            ? { ...w, status: "completed", updated_at: new Date().toISOString() }
            : w,
        ),
      );
      try {
        const resp = await apiFetch(`/chats/${chatId}`, {
          method: "PATCH",
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
    async (chatId: string) => {
      setWorkloads((prev) =>
        prev.map((w) =>
          w.id === chatId
            ? { ...w, status: "needs_attention", updated_at: new Date().toISOString() }
            : w,
        ),
      );
      try {
        const resp = await apiFetch(`/chats/${chatId}/interrupt`, {
          method: "POST",
        });
        if (!resp.ok) refreshWorkloads();
      } catch {
        refreshWorkloads();
      }
    },
    [refreshWorkloads],
  );

  const handleLinkClick = useCallback(
    (url: string) => {
      const adminMatch = url.match(/^\/admin\/chats\/(.+)$/);
      if (adminMatch && onNavigateAdmin) {
        onNavigateAdmin(adminMatch[1]);
      }
    },
    [onNavigateAdmin],
  );

  // Find workload for the active chat (if viewing a workload chat)
  const activeWorkload = workloads.find((w) => w.id === activeChatId);

  const dispatchedIds = useMemo(
    () => new Set(workloads.map((w) => w.dispatch_id).filter(Boolean) as string[]),
    [workloads],
  );

  return (
    <div className={styles.container}>
      <div className={styles.tabs}>
        <button
          className={clsx(styles.tab, styles.tabMain, activeChatId === room.primary_chat_id && styles.tabActive)}
          onClick={() => setActiveChatId(room.primary_chat_id)}
        >
          Main
        </button>
        {workloads.filter((w) => !hiddenTabs.has(w.id)).map((w) => (
          <div key={w.id} className={clsx(styles.tab, activeChatId === w.id && styles.tabActive)}>
            <button
              className={styles.tabLabel}
              onClick={() => setActiveChatId(w.id)}
            >
              {w.owner_name}: {w.title}
            </button>
            {(w.status === "needs_attention" || w.status === "awaiting_approval") && w.id !== activeChatId && (
              <span className={styles.attentionDot} />
            )}
            <button
              className={styles.tabClose}
              onClick={(e) => {
                e.stopPropagation();
                setHiddenTabs((prev) => new Set(prev).add(w.id));
                if (activeChatId === w.id) setActiveChatId(room.primary_chat_id);
              }}
              aria-label={`Close ${w.title}`}
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <line x1="18" y1="6" x2="6" y2="18" />
                <line x1="6" y1="6" x2="18" y2="18" />
              </svg>
            </button>
          </div>
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
          projectId={projectId}
          placeholder={`Message ${room.name}...`}
          onAiMessage={activeChatId === room.primary_chat_id ? refreshWorkloads : undefined}
          onRoomEvent={handleRoomEvent}
          onLinkClick={handleLinkClick}
          workloadStatus={activeWorkload?.status}
          workloadHasSession={activeWorkload?.has_session}
          permissionMode={activeWorkload?.permission_mode}
          dispatchedIds={dispatchedIds}
          onInterrupt={
            activeWorkload
              ? () => handleInterrupt(activeWorkload.id)
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
              onNavigateAdmin={onNavigateAdmin}
            />
          )}
        </div>
      </div>
    </div>
  );
}
