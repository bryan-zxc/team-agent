"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import clsx from "clsx";
import type { IDockviewPanelProps } from "dockview";
import type { AdminChat, Member } from "@/types";
import { apiFetch } from "@/lib/api";
import { ChatView } from "./ChatView";
import styles from "./AdminTab.module.css";
// Reuse ModeToggleStrip styles for the local-only mode toggle in landing state
import modeStyles from "./ModeToggleStrip.module.css";

type ContentBlock =
  | { type: "text"; value: string }
  | { type: "mention"; member_id: string; display_name: string }
  | { type: "skill"; name: string };

type AdminTabParams = {
  projectId: string;
  memberId: string | null;
  members: Member[];
  adminRoomId: string;
  onAdminChatsChanged: (chats: AdminChat[]) => void;
  viewHistoryChatId?: string | null;
};

export function AdminTab({ params }: IDockviewPanelProps<AdminTabParams>) {
  const { projectId, memberId, members, adminRoomId, onAdminChatsChanged, viewHistoryChatId } = params;
  const [activeChatId, setActiveChatId] = useState<string | null>(null);
  const [permissionMode, setPermissionMode] = useState<"default" | "acceptEdits">("acceptEdits");
  const [chatStatus, setChatStatus] = useState<string | undefined>(undefined);
  const [isCreating, setIsCreating] = useState(false);
  const [viewingHistoryChatId, setViewingHistoryChatId] = useState<string | null>(null);
  const [initialMessage, setInitialMessage] = useState<{ blocks: ContentBlock[]; mentions: string[] } | null>(null);
  const mountedRef = useRef(false);

  // Respond to external request to view a history chat
  useEffect(() => {
    if (viewHistoryChatId) {
      setViewingHistoryChatId(viewHistoryChatId);
      setActiveChatId(null);
    }
  }, [viewHistoryChatId]);

  const refreshAdminChats = useCallback(async () => {
    try {
      const res = await apiFetch(`/projects/${projectId}/admin-room`);
      const data = await res.json();
      onAdminChatsChanged(data.chats ?? []);
      return data.chats as AdminChat[];
    } catch {
      return [];
    }
  }, [projectId, onAdminChatsChanged]);

  // On mount: fetch chats and auto-resume any running session
  useEffect(() => {
    if (mountedRef.current) return;
    mountedRef.current = true;
    refreshAdminChats().then((chats) => {
      const running = chats.find(
        (c: AdminChat) => c.status === "running" || c.status === "needs_attention",
      );
      if (running) {
        setActiveChatId(running.id);
        setChatStatus(running.status);
      }
    });
  }, [refreshAdminChats]);

  const handleRoomEvent = useCallback(
    (event: Record<string, unknown>) => {
      if (event._event === "admin_status" || event._event === "workload_status") {
        const status = event.status as string;
        setChatStatus(status);
        if (event.permission_mode) {
          setPermissionMode(event.permission_mode as "default" | "acceptEdits");
        }
        refreshAdminChats();
      }
    },
    [refreshAdminChats],
  );

  const handleFirstMessage = useCallback(
    async (blocks: ContentBlock[], mentions: string[]) => {
      if (isCreating) return;
      setIsCreating(true);
      try {
        const res = await apiFetch(`/projects/${projectId}/admin-room/chats`, {
          method: "POST",
          body: JSON.stringify({ permission_mode: permissionMode }),
        });
        const data = await res.json();
        setActiveChatId(data.id);
        setChatStatus("running");
        setInitialMessage({ blocks, mentions });
        refreshAdminChats();
      } finally {
        setIsCreating(false);
      }
    },
    [projectId, permissionMode, isCreating, refreshAdminChats],
  );

  const handleCancel = useCallback(async () => {
    if (!activeChatId) return;
    try {
      await apiFetch(`/chats/${activeChatId}/cancel`, { method: "POST" });
    } catch { /* ignore */ }
    setActiveChatId(null);
    setChatStatus(undefined);
    setInitialMessage(null);
    refreshAdminChats();
  }, [activeChatId, refreshAdminChats]);

  const handleBackToLanding = useCallback(() => {
    setViewingHistoryChatId(null);
  }, []);

  const isVibe = permissionMode === "acceptEdits";

  // Mode: History view
  if (viewingHistoryChatId) {
    return (
      <div className={styles.container}>
        <div className={styles.historyBar}>
          <button className={styles.backBtn} onClick={handleBackToLanding}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="15 18 9 12 15 6" />
            </svg>
            Back
          </button>
        </div>
        <div className={styles.body}>
          <ChatView
            key={viewingHistoryChatId}
            chatId={viewingHistoryChatId}
            memberId={memberId}
            members={members}
            projectId={projectId}
            placeholder=""
            readOnly
          />
        </div>
      </div>
    );
  }

  // Mode: Active session
  if (activeChatId) {
    return (
      <div className={styles.container}>
        <div className={styles.body}>
          <ChatView
            key={activeChatId}
            chatId={activeChatId}
            memberId={memberId}
            members={members}
            projectId={projectId}
            placeholder="Message admin session..."
            onRoomEvent={handleRoomEvent}
            workloadStatus={chatStatus}
            workloadHasSession
            permissionMode={permissionMode}
            onInterrupt={handleCancel}
            initialMessage={initialMessage ?? undefined}
          />
        </div>
      </div>
    );
  }

  // Local mode toggle for landing state (no chatId, so ModeToggleStrip can't be used)
  const localModeToggle = (
    <div className={clsx(modeStyles.strip, isVibe && modeStyles.stripVibe)}>
      {isVibe && (
        <svg className={modeStyles.zapIcon} width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
        </svg>
      )}
      <span className={clsx(modeStyles.label, isVibe && modeStyles.labelVibe)}>
        {isVibe ? "Vibe coding" : "Standard mode"}
      </span>
      <button
        className={clsx(modeStyles.toggle, isVibe && modeStyles.toggleOn)}
        onClick={() => setPermissionMode((m) => (m === "acceptEdits" ? "default" : "acceptEdits"))}
        aria-label={`Switch to ${isVibe ? "standard" : "vibe coding"} mode`}
      />
      <span className={clsx(modeStyles.desc, isVibe && modeStyles.descVibe)}>
        {isVibe ? "All file edits auto-accepted" : "File edits require approval"}
      </span>
    </div>
  );

  // Mode: Landing (no active session)
  return (
    <div className={styles.container}>
      <div className={styles.body}>
        <ChatView
          chatId={null}
          memberId={memberId}
          members={members}
          projectId={projectId}
          placeholder="Start an admin session..."
          onFirstMessage={handleFirstMessage}
          inputPrefix={localModeToggle}
        />
      </div>
    </div>
  );
}
