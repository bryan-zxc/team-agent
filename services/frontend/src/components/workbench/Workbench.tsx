"use client";

import clsx from "clsx";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { DockviewReact, type DockviewApi, type DockviewReadyEvent, type IDockviewPanelProps, type IWatermarkPanelProps } from "dockview";
import { TabIcon } from "./TabIcon";
import "dockview/dist/styles/dockview.css";
import "./dockview-theme.css";
import { ActivityBar, type Panel } from "./ActivityBar";
import { ChatSidePanel } from "./ChatSidePanel";
import { FilesSidePanel } from "./FilesSidePanel";
import { MembersSidePanel } from "./MembersSidePanel";
import { AdminSidePanel } from "./AdminSidePanel";
import { FavouritesSidePanel } from "./FavouritesSidePanel";
import { ChatTab } from "./ChatTab";
import { FileTab } from "./FileTab";
import { MemberProfileTab } from "./MemberProfileTab";
import { TerminalTab } from "./TerminalTab";
import { LiveViewTab } from "./LiveViewTab";
import { AdminTab } from "./AdminTab";
import { SqlTab } from "./SqlTab";
import { DataTableTab } from "./DataTableTab";
import { DataSidePanel } from "./DataSidePanel";
import { ProjectTopBar } from "./ProjectTopBar";
import { AddMemberModal } from "@/components/members/AddMemberModal";
import { useAuth } from "@/hooks/useAuth";
import { AttentionProvider } from "@/hooks/useAttention";
import { apiFetch } from "@/lib/api";
import type { AdminChat, Member, Project, Room } from "@/types";
import styles from "./Workbench.module.css";

type WorkbenchProps = {
  projectId: string;
};

function Watermark({ containerApi }: IWatermarkPanelProps) {
  return (
    <div className={styles.watermark}>
      <p className={styles.watermarkText}>Open a room or file to get started</p>
    </div>
  );
}

const components: Record<string, React.FunctionComponent<IDockviewPanelProps<any>>> = {
  chatTab: ChatTab,
  fileTab: FileTab,
  memberTab: MemberProfileTab,
  terminalTab: TerminalTab,
  liveViewTab: LiveViewTab,
  adminTab: AdminTab,
  sqlTab: SqlTab,
  dataTableTab: DataTableTab,
};

export function Workbench({ projectId }: WorkbenchProps) {
  const { user: authUser } = useAuth();
  const [activePanel, setActivePanel] = useState<Panel>("chat");
  const [panelCollapsed, setPanelCollapsed] = useState(false);
  const [rooms, setRooms] = useState<Room[]>([]);
  const [members, setMembers] = useState<Member[]>([]);
  const [memberId, setMemberId] = useState<string | null>(null);
  const [showAddModal, setShowAddModal] = useState(false);
  const [activeRoomId, setActiveRoomId] = useState<string | undefined>();
  const [project, setProject] = useState<Project | null>(null);
  const [adminRoomId, setAdminRoomId] = useState<string | null>(null);
  const [adminChats, setAdminChats] = useState<AdminChat[]>([]);
  const [adminHistoryChatId, setAdminHistoryChatId] = useState<string | null>(null);
  const [attentionRoomIds, setAttentionRoomIds] = useState<Set<string>>(new Set());
  const apiRef = useRef<DockviewApi | null>(null);

  const isLocked = project?.is_locked ?? false;
  const adminNeedsAttention = adminChats.some(
    (c) => c.status === "running" || c.status === "needs_attention" || c.status === "awaiting_approval",
  );

  const attentionValue = useMemo(
    () => ({ attentionRoomIds, adminNeedsAttention }),
    [attentionRoomIds, adminNeedsAttention],
  );

  const handleAttentionChange = useCallback((roomId: string, needsAttention: boolean) => {
    setAttentionRoomIds((prev) => {
      if (needsAttention && prev.has(roomId)) return prev;
      if (!needsAttention && !prev.has(roomId)) return prev;
      const next = new Set(prev);
      if (needsAttention) {
        next.add(roomId);
      } else {
        next.delete(roomId);
      }
      return next;
    });
  }, []);

  useEffect(() => {
    apiFetch(`/projects/${projectId}`).then((r) => r.json()).then(setProject).catch(() => {});
    apiFetch(`/projects/${projectId}/rooms`).then((r) => r.json()).then(setRooms).catch(() => {});
    apiFetch(`/projects/${projectId}/members`).then((r) => r.json()).then(setMembers).catch(() => {});
    apiFetch(`/projects/${projectId}/admin-room`)
      .then((r) => r.json())
      .then((data) => {
        setAdminRoomId(data.id);
        setAdminChats(data.chats ?? []);
      })
      .catch(() => {});

    // Check manifest on project entry
    apiFetch(`/projects/${projectId}/check-manifest`, { method: "POST" })
      .then((r) => r.json())
      .then((data) => {
        if (data.is_locked) {
          setProject((prev) => prev ? { ...prev, is_locked: true, lock_reason: data.reason } : prev);
        }
      })
      .catch(() => {});
  }, [projectId]);

  useEffect(() => {
    if (authUser && members.length > 0) {
      const match = members.find((m) => m.user_id === authUser.id);
      if (match) setMemberId(match.id);
    }
  }, [members, authUser]);

  const currentMember = members.find((m) => m.id === memberId) ?? null;
  const coordinator = members.find((m) => m.type === "coordinator");

  const openRoom = useCallback(
    (roomId: string) => {
      const api = apiRef.current;
      if (!api) return;

      const room = rooms.find((r) => r.id === roomId);
      if (!room) return;

      const panelId = `room-${roomId}`;
      const existing = api.panels.find((p) => p.id === panelId);
      if (existing) {
        // Only call setActive() when the panel isn't already active — dockview's
        // setActive() toggles panel visibility which resets scroll position.
        if (!existing.api.isActive) {
          existing.api.setActive();
        }
        // Always scroll the chat to the bottom on room click
        requestAnimationFrame(() => {
          const container = document.querySelector<HTMLElement>('[class*="messages"]');
          if (container && container.clientHeight > 0) {
            container.scrollTop = container.scrollHeight;
          }
        });
        setActiveRoomId(roomId);
        return;
      }

      api.addPanel({
        id: panelId,
        component: "chatTab",
        title: room.name,
        params: { roomId, room, memberId, members, projectId, onScreencastStarted: openLiveView, onNavigateAdmin: navigateToAdmin, onAttentionChange: handleAttentionChange },
      });
      setActiveRoomId(roomId);
    },
    [rooms, memberId, members],
  );

  const closeStaleTabsForPath = useCallback((filePath: string, keepPanelId: string) => {
    const api = apiRef.current;
    if (!api) return;
    for (const panel of api.panels) {
      if (panel.id === keepPanelId) continue;
      const p = panel.params as any;
      if (p?.filePath === filePath) {
        api.removePanel(panel);
      }
    }
  }, []);

  const openFile = useCallback(
    (filePath: string) => {
      const api = apiRef.current;
      if (!api) return;

      // Check by panel ID first, then by filePath param (covers saved SQL tabs)
      const panelId = `file-${filePath}`;
      const existing =
        api.panels.find((p) => p.id === panelId) ??
        api.panels.find((p) => (p.params as any)?.filePath === filePath);
      if (existing) {
        existing.api.setActive();
        return;
      }

      const fileName = filePath.split("/").pop() ?? filePath;
      const isSql = fileName.endsWith(".sql");
      api.addPanel({
        id: panelId,
        component: isSql ? "sqlTab" : "fileTab",
        title: fileName,
        params: isSql
          ? { filePath, projectId, database: "data", onSavedOverwrite: closeStaleTabsForPath }
          : { filePath, projectId, onOpenFile: openFile },
      });
    },
    [projectId, closeStaleTabsForPath],
  );

  const handleCreateRoom = useCallback(
    async (name: string) => {
      const res = await apiFetch(`/projects/${projectId}/rooms`, {
        method: "POST",
        body: JSON.stringify({ name }),
      });
      const room: Room = await res.json();
      setRooms((prev) => [...prev, room]);
    },
    [projectId],
  );

  const handleRenameRoom = useCallback(
    async (roomId: string, newName: string) => {
      const res = await apiFetch(`/projects/${projectId}/rooms/${roomId}`, {
        method: "PATCH",
        body: JSON.stringify({ name: newName }),
      });
      const updated: Room = await res.json();
      setRooms((prev) => prev.map((r) => (r.id === updated.id ? updated : r)));

      // Update tab title if the room is open
      const api = apiRef.current;
      if (api) {
        const panel = api.panels.find((p) => p.id === `room-${roomId}`);
        if (panel) {
          panel.api.updateParameters({ room: updated });
          panel.setTitle(updated.name);
        }
      }
    },
    [projectId],
  );

  const openLiveView = useCallback((chatId: string, title = "Live View") => {
    const api = apiRef.current;
    if (!api) return;

    const panelId = `liveview-${chatId}`;
    const existing = api.panels.find((p) => p.id === panelId);
    if (existing) {
      existing.api.setActive();
      return;
    }

    const closeLiveView = () => {
      const dockApi = apiRef.current;
      if (!dockApi) return;
      const panel = dockApi.panels.find((p) => p.id === panelId);
      if (panel) dockApi.removePanel(panel);
    };

    api.addPanel({
      id: panelId,
      component: "liveViewTab",
      title,
      params: { chatId, onClose: closeLiveView },
    });
  }, []);

  const openTerminal = useCallback(() => {
    const api = apiRef.current;
    if (!api) return;

    const panelId = `terminal-${Date.now()}`;
    api.addPanel({
      id: panelId,
      component: "terminalTab",
      title: "Terminal",
      params: { projectId },
    });
  }, [projectId]);

  const openSqlTab = useCallback(
    (database: string) => {
      const api = apiRef.current;
      if (!api) return;

      const tabId = `sql-${Date.now()}`;
      api.addPanel({
        id: tabId,
        component: "sqlTab",
        title: "New Query",
        params: { projectId, database, onSavedOverwrite: closeStaleTabsForPath },
      });
    },
    [projectId, closeStaleTabsForPath],
  );

  const openTable = useCallback(
    (database: string, tableName: string) => {
      const api = apiRef.current;
      if (!api) return;

      const panelId = `table-${database}-${tableName}`;
      const existing = api.panels.find((p) => p.id === panelId);
      if (existing) {
        existing.api.setActive();
        return;
      }

      api.addPanel({
        id: panelId,
        component: "dataTableTab",
        title: tableName,
        params: { projectId, database, tableName },
      });
    },
    [projectId],
  );

  const closeAdminTab = useCallback(() => {
    const api = apiRef.current;
    if (!api) return;
    const panel = api.panels.find((p) => p.id === "admin-session");
    if (panel) api.removePanel(panel);
  }, []);

  // Open or focus the admin Dockview tab
  const openAdminTab = useCallback(() => {
    const api = apiRef.current;
    if (!api || !adminRoomId) return;

    const panelId = "admin-session";
    const existing = api.panels.find((p) => p.id === panelId);
    if (existing) {
      if (!existing.api.isActive) {
        existing.api.setActive();
      }
      // Always scroll the chat to the bottom on admin tab click
      requestAnimationFrame(() => {
        const container = document.querySelector<HTMLElement>('[class*="messages"]');
        if (container && container.clientHeight > 0) {
          container.scrollTop = container.scrollHeight;
        }
      });
      return;
    }

    api.addPanel({
      id: panelId,
      component: "adminTab",
      title: "Admin",
      params: {
        projectId,
        memberId,
        members,
        adminRoomId,
        onAdminChatsChanged: setAdminChats,
        onSessionComplete: closeAdminTab,
        viewHistoryChatId: null,
      },
    });
  }, [projectId, memberId, members, adminRoomId, closeAdminTab]);

  // Auto-open admin tab when switching to admin panel
  useEffect(() => {
    if (activePanel === "admin" && adminRoomId) {
      openAdminTab();
    }
  }, [activePanel, adminRoomId, openAdminTab]);

  // When a history chat is clicked in the side panel, update the admin tab params
  const handleAdminChatClick = useCallback(
    (chatId: string) => {
      const api = apiRef.current;
      if (!api) return;

      const panelId = "admin-session";
      const existing = api.panels.find((p) => p.id === panelId);
      if (existing) {
        existing.api.setActive();
        existing.api.updateParameters({ viewHistoryChatId: chatId });
      } else {
        // Tab not open — open it with the history view
        api.addPanel({
          id: panelId,
          component: "adminTab",
          title: "Admin",
          params: {
            projectId,
            memberId,
            members,
            adminRoomId,
            onAdminChatsChanged: setAdminChats,
            onSessionComplete: closeAdminTab,
            viewHistoryChatId: chatId,
          },
        });
      }
    },
    [projectId, memberId, members, adminRoomId, closeAdminTab],
  );

  const navigateToAdmin = useCallback((chatId?: string) => {
    setActivePanel("admin");
    setPanelCollapsed(false);
    if (chatId) {
      // Defer so the admin panel has time to mount before we update params
      setTimeout(() => handleAdminChatClick(chatId), 0);
    }
  }, [handleAdminChatClick]);

  const handlePanelChange = useCallback((panel: Panel) => {
    if (panel === activePanel && !panelCollapsed) {
      setPanelCollapsed(true);
    } else {
      setActivePanel(panel);
      setPanelCollapsed(false);
    }
  }, [activePanel, panelCollapsed]);

  const handleReady = useCallback((event: DockviewReadyEvent) => {
    apiRef.current = event.api;

    event.api.onDidActivePanelChange((e) => {
      if (e?.id?.startsWith("room-")) {
        setActiveRoomId(e.id.replace("room-", ""));
      } else {
        setActiveRoomId(undefined);
      }
    });

    event.api.onDidRemovePanel((panel) => {
      if (panel.id.startsWith("room-")) {
        const removedRoomId = panel.id.replace("room-", "");
        setAttentionRoomIds((prev) => {
          if (!prev.has(removedRoomId)) return prev;
          const next = new Set(prev);
          next.delete(removedRoomId);
          return next;
        });
      }
    });
  }, []);

  return (
    <div className={clsx(styles.workbench, panelCollapsed && styles.workbenchCollapsed)}>
      {project && (
        <ProjectTopBar
          project={project}
          projectId={projectId}
          onBranchChange={setProject}
        />
      )}

      {isLocked && (
        <div className={styles.lockdownBanner}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
            <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
            <path d="M7 11V7a5 5 0 0 1 10 0v4" />
          </svg>
          <span>
            <strong>Project locked</strong>
            {project?.lock_reason ? ` \u2014 ${project.lock_reason}` : ""}
          </span>
        </div>
      )}

      <ActivityBar
        activePanel={activePanel}
        onPanelChange={handlePanelChange}
        onOpenTerminal={openTerminal}
        coordinatorInitial={coordinator?.display_name?.[0]}
        coordinatorAvatar={coordinator?.avatar}
        chatBadge={[...attentionRoomIds].some((id) => id !== activeRoomId)}
        adminBadge={adminNeedsAttention && activePanel !== "admin"}
      />

      <aside className={clsx(styles.sidePanel, panelCollapsed && styles.sidePanelCollapsed)}>
        {!panelCollapsed && (
          activePanel === "chat" ? (
            <ChatSidePanel
              rooms={rooms}
              activeRoomId={activeRoomId}
              onRoomClick={openRoom}
              onCreateRoom={isLocked ? undefined : handleCreateRoom}
              onRenameRoom={isLocked ? undefined : handleRenameRoom}
              currentMember={currentMember}
              attentionRoomIds={attentionRoomIds}
            />
          ) : activePanel === "data" ? (
            <DataSidePanel projectId={projectId} onOpenTable={openTable} onOpenSqlTab={openSqlTab} />
          ) : activePanel === "favourites" ? (
            <FavouritesSidePanel projectId={projectId} onFileClick={openFile} />
          ) : activePanel === "members" ? (
            <MembersSidePanel
              members={members}
              onAddMember={isLocked ? undefined : () => setShowAddModal(true)}
              onMemberClick={(id) => {
                const api = apiRef.current;
                if (!api) return;

                const panelId = `member-${id}`;
                const existing = api.panels.find((p) => p.id === panelId);
                if (existing) {
                  existing.api.setActive();
                  return;
                }

                const member = members.find((m) => m.id === id);
                if (!member) return;

                api.addPanel({
                  id: panelId,
                  component: "memberTab",
                  title: member.display_name,
                  params: { projectId, memberId: id, memberName: member.display_name },
                });
              }}
            />
          ) : activePanel === "admin" ? (
            <AdminSidePanel
              adminChats={adminChats}
              onChatClick={handleAdminChatClick}
              currentMember={currentMember}
            />
          ) : (
            <FilesSidePanel projectId={projectId} onFileClick={openFile} />
          )
        )}
      </aside>

      <main className={styles.editorArea}>
        <AttentionProvider value={attentionValue}>
          <DockviewReact
            className="ta-dockview"
            components={components}
            defaultTabComponent={TabIcon}
            watermarkComponent={Watermark}
            onReady={handleReady}
          />
        </AttentionProvider>
      </main>

      <AddMemberModal
        open={showAddModal}
        projectId={projectId}
        onClose={() => setShowAddModal(false)}
        onMemberAdded={(member) => setMembers((prev) => [...prev, member])}
      />
    </div>
  );
}
