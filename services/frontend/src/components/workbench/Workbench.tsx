"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { DockviewReact, type DockviewApi, type DockviewReadyEvent, type IDockviewPanelProps, type IWatermarkPanelProps } from "dockview";
import "dockview/dist/styles/dockview.css";
import "./dockview-theme.css";
import { ActivityBar } from "./ActivityBar";
import { ChatSidePanel } from "./ChatSidePanel";
import { FilesSidePanel } from "./FilesSidePanel";
import { ChatTab } from "./ChatTab";
import { FileTab } from "./FileTab";
import { AddMemberModal } from "@/components/members/AddMemberModal";
import type { Member, Room } from "@/types";
import styles from "./Workbench.module.css";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type Panel = "chat" | "files";

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
};

export function Workbench({ projectId }: WorkbenchProps) {
  const [activePanel, setActivePanel] = useState<Panel>("chat");
  const [rooms, setRooms] = useState<Room[]>([]);
  const [members, setMembers] = useState<Member[]>([]);
  const [memberId, setMemberId] = useState<string | null>(null);
  const [showAddModal, setShowAddModal] = useState(false);
  const [activeRoomId, setActiveRoomId] = useState<string | undefined>();
  const apiRef = useRef<DockviewApi | null>(null);

  useEffect(() => {
    fetch(`${API_URL}/projects/${projectId}/rooms`).then((r) => r.json()).then(setRooms);
    fetch(`${API_URL}/projects/${projectId}/members`).then((r) => r.json()).then(setMembers);
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
        title: `💬 ${room.name}`,
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
          panel.setTitle(`💬 ${updated.name}`);
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
      <ActivityBar activePanel={activePanel} onPanelChange={setActivePanel} />

      <aside className={styles.sidePanel}>
        {activePanel === "chat" ? (
          <ChatSidePanel
            rooms={rooms}
            members={members}
            activeRoomId={activeRoomId}
            onRoomClick={openRoom}
            onCreateRoom={handleCreateRoom}
            onRenameRoom={handleRenameRoom}
            onAddMember={() => setShowAddModal(true)}
            onMemberClick={(id) => {
              /* future: open member profile tab */
            }}
            currentMember={currentMember}
          />
        ) : (
          <FilesSidePanel projectId={projectId} onFileClick={openFile} />
        )}
      </aside>

      <main className={styles.editorArea}>
        <DockviewReact
          className="ta-dockview"
          components={components}
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
