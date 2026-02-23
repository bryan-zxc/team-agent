"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { DockviewReact, type DockviewApi, type DockviewReadyEvent, type IDockviewPanelProps, type IWatermarkPanelProps } from "dockview";
import { TabIcon } from "./TabIcon";
import "dockview/dist/styles/dockview.css";
import "./dockview-theme.css";
import { ActivityBar } from "./ActivityBar";
import { ChatSidePanel } from "./ChatSidePanel";
import { FilesSidePanel } from "./FilesSidePanel";
import { MembersSidePanel } from "./MembersSidePanel";
import { ChatTab } from "./ChatTab";
import { FileTab } from "./FileTab";
import { MemberProfileTab } from "./MemberProfileTab";
import { AddMemberModal } from "@/components/members/AddMemberModal";
import type { Member, Project, Room } from "@/types";
import styles from "./Workbench.module.css";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type Panel = "chat" | "files" | "members";

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
};

export function Workbench({ projectId }: WorkbenchProps) {
  const [activePanel, setActivePanel] = useState<Panel>("chat");
  const [rooms, setRooms] = useState<Room[]>([]);
  const [members, setMembers] = useState<Member[]>([]);
  const [memberId, setMemberId] = useState<string | null>(null);
  const [showAddModal, setShowAddModal] = useState(false);
  const [activeRoomId, setActiveRoomId] = useState<string | undefined>();
  const [project, setProject] = useState<Project | null>(null);
  const apiRef = useRef<DockviewApi | null>(null);

  const isLocked = project?.is_locked ?? false;

  useEffect(() => {
    fetch(`${API_URL}/projects/${projectId}`).then((r) => r.json()).then(setProject);
    fetch(`${API_URL}/projects/${projectId}/rooms`).then((r) => r.json()).then(setRooms);
    fetch(`${API_URL}/projects/${projectId}/members`).then((r) => r.json()).then(setMembers);

    // Check manifest on project entry
    fetch(`${API_URL}/projects/${projectId}/check-manifest`, { method: "POST" })
      .then((r) => r.json())
      .then((data) => {
        if (data.is_locked) {
          setProject((prev) => prev ? { ...prev, is_locked: true, lock_reason: data.reason } : prev);
        }
      })
      .catch(() => {});
  }, [projectId]);

  useEffect(() => {
    const userId = typeof window !== "undefined" ? localStorage.getItem("user_id") : null;
    if (userId && members.length > 0) {
      const match = members.find((m) => m.user_id === userId);
      if (match) setMemberId(match.id);
    }
  }, [members]);

  const currentMember = members.find((m) => m.id === memberId) ?? null;

  const openRoom = useCallback(
    (roomId: string) => {
      const api = apiRef.current;
      if (!api) return;

      const room = rooms.find((r) => r.id === roomId);
      if (!room) return;

      const panelId = `room-${roomId}`;
      const existing = api.panels.find((p) => p.id === panelId);
      if (existing) {
        existing.api.setActive();
        setActiveRoomId(roomId);
        return;
      }

      api.addPanel({
        id: panelId,
        component: "chatTab",
        title: room.name,
        params: { roomId, room, memberId, members },
      });
      setActiveRoomId(roomId);
    },
    [rooms, memberId, members],
  );

  const openFile = useCallback(
    (filePath: string) => {
      const api = apiRef.current;
      if (!api) return;

      const panelId = `file-${filePath}`;
      const existing = api.panels.find((p) => p.id === panelId);
      if (existing) {
        existing.api.setActive();
        return;
      }

      const fileName = filePath.split("/").pop() ?? filePath;
      api.addPanel({
        id: panelId,
        component: "fileTab",
        title: fileName,
        params: { filePath, projectId },
      });
    },
    [projectId],
  );

  const handleCreateRoom = useCallback(
    async (name: string) => {
      const res = await fetch(`${API_URL}/projects/${projectId}/rooms`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name }),
      });
      const room: Room = await res.json();
      setRooms((prev) => [...prev, room]);
    },
    [projectId],
  );

  const handleRenameRoom = useCallback(
    async (roomId: string, newName: string) => {
      const res = await fetch(`${API_URL}/projects/${projectId}/rooms/${roomId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
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

  const handleReady = useCallback((event: DockviewReadyEvent) => {
    apiRef.current = event.api;

    event.api.onDidActivePanelChange((e) => {
      if (e?.id?.startsWith("room-")) {
        setActiveRoomId(e.id.replace("room-", ""));
      } else {
        setActiveRoomId(undefined);
      }
    });
  }, []);

  return (
    <div className={styles.workbench}>
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

      <ActivityBar activePanel={activePanel} onPanelChange={setActivePanel} />

      <aside className={styles.sidePanel}>
        {activePanel === "chat" ? (
          <ChatSidePanel
            rooms={rooms}
            activeRoomId={activeRoomId}
            onRoomClick={openRoom}
            onCreateRoom={isLocked ? undefined : handleCreateRoom}
            onRenameRoom={isLocked ? undefined : handleRenameRoom}
            currentMember={currentMember}
          />
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
        ) : (
          <FilesSidePanel projectId={projectId} onFileClick={openFile} />
        )}
      </aside>

      <main className={styles.editorArea}>
        <DockviewReact
          className="ta-dockview"
          components={components}
          defaultTabComponent={TabIcon}
          watermarkComponent={Watermark}
          onReady={handleReady}
        />
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
