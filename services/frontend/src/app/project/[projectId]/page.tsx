"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import clsx from "clsx";
import { Sidebar } from "@/components/sidebar/Sidebar";
import { AddMemberModal } from "@/components/members/AddMemberModal";
import type { Member, Room } from "@/types";
import styles from "./page.module.css";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function ProjectDashboard() {
  const params = useParams<{ projectId: string }>();
  const router = useRouter();

  const [rooms, setRooms] = useState<Room[]>([]);
  const [members, setMembers] = useState<Member[]>([]);
  const [newRoomName, setNewRoomName] = useState("");
  const [showAddModal, setShowAddModal] = useState(false);

  const userId = typeof window !== "undefined" ? localStorage.getItem("user_id") : null;
  const currentMember = members.find((m) => m.user_id === userId);

  useEffect(() => {
    if (!params.projectId) return;
    fetch(`${API_URL}/projects/${params.projectId}/rooms`).then((r) => r.json()).then(setRooms);
    fetch(`${API_URL}/projects/${params.projectId}/members`).then((r) => r.json()).then(setMembers);
  }, [params.projectId]);

  const createRoom = useCallback(async () => {
    if (!newRoomName.trim()) return;
    const res = await fetch(`${API_URL}/projects/${params.projectId}/rooms`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: newRoomName.trim() }),
    });
    const room: Room = await res.json();
    setRooms((prev) => [...prev, room]);
    setNewRoomName("");
  }, [newRoomName, params.projectId]);

  const openRoom = useCallback(
    (roomId: string) => {
      router.push(`/project/${params.projectId}/chat/${roomId}`);
    },
    [params.projectId, router],
  );

  return (
    <div className={styles.layout}>
      <Sidebar
        rooms={rooms}
        members={members}
        onRoomClick={openRoom}
        onAddMember={() => setShowAddModal(true)}
        onMemberClick={(id) => router.push(`/project/${params.projectId}/members/${id}`)}
        roomActions={
          <div className={styles.newRoom}>
            <input
              className={styles.newRoomInput}
              placeholder="New room name..."
              value={newRoomName}
              onChange={(e) => setNewRoomName(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && createRoom()}
            />
            <button className={styles.newRoomBtn} onClick={createRoom} aria-label="Create room">+</button>
          </div>
        }
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
        <div className={styles.welcome}>
          <h2 className={styles.welcomeTitle}>Welcome</h2>
          <p className={styles.welcomeText}>Select a room to start chatting.</p>
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
