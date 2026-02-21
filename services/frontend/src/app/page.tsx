"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import clsx from "clsx";
import { Sidebar } from "@/components/sidebar/Sidebar";
import { AddMemberModal } from "@/components/members/AddMemberModal";
import type { Member, Room, User } from "@/types";
import styles from "./page.module.css";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function Home() {
  const router = useRouter();
  const [rooms, setRooms] = useState<Room[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [members, setMembers] = useState<Member[]>([]);
  const [selectedUser, setSelectedUser] = useState<string | null>(null);
  const [newRoomName, setNewRoomName] = useState("");
  const [showUserPicker, setShowUserPicker] = useState(false);
  const [showAddModal, setShowAddModal] = useState(false);

  useEffect(() => {
    fetch(`${API_URL}/rooms`).then((r) => r.json()).then(setRooms);
    fetch(`${API_URL}/users`).then((r) => r.json()).then(setUsers);
    fetch(`${API_URL}/members`).then((r) => r.json()).then(setMembers);
    const stored = localStorage.getItem("member_id");
    if (stored) setSelectedUser(stored);
  }, []);

  const currentUser = users.find((u) => u.id === selectedUser);

  const selectUser = useCallback((id: string) => {
    setSelectedUser(id);
    localStorage.setItem("member_id", id);
    setShowUserPicker(false);
  }, []);

  const createRoom = useCallback(async () => {
    if (!newRoomName.trim()) return;
    const res = await fetch(`${API_URL}/rooms`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: newRoomName.trim() }),
    });
    const room: Room = await res.json();
    setRooms((prev) => [...prev, room]);
    setNewRoomName("");
  }, [newRoomName]);

  const openRoom = useCallback(
    (roomId: string) => {
      if (!selectedUser) {
        setShowUserPicker(true);
        return;
      }
      router.push(`/chat/${roomId}`);
    },
    [selectedUser, router],
  );

  return (
    <div className={styles.layout}>
      <Sidebar
        rooms={rooms}
        members={members}
        onRoomClick={openRoom}
        onAddMember={() => setShowAddModal(true)}
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
        <div className={styles.sidebarFooter}>
          <button
            className={styles.userSelector}
            onClick={() => setShowUserPicker(!showUserPicker)}
          >
            {currentUser ? (
              <>
                <div className={clsx(styles.avatar, currentUser.type === "ai" ? styles.avatarAi : styles.avatarHuman)}>
                  {currentUser.display_name[0]}
                </div>
                <div className={styles.userInfo}>
                  <div className={styles.userName}>{currentUser.display_name}</div>
                  <div className={styles.userRole}>{currentUser.type}</div>
                </div>
              </>
            ) : (
              <div className={styles.userInfo}>
                <div className={styles.userName}>Select a user</div>
              </div>
            )}
            <span className={styles.chevron}>{showUserPicker ? "\u25B2" : "\u25BC"}</span>
          </button>

          {showUserPicker && (
            <div className={styles.userDropdown}>
              {users.filter((u) => u.type === "human").map((user) => (
                <button
                  key={user.id}
                  className={styles.userOption}
                  onClick={() => selectUser(user.id)}
                >
                  <div className={clsx(styles.avatar, styles.avatarHuman)}>
                    {user.display_name[0]}
                  </div>
                  <span>{user.display_name}</span>
                </button>
              ))}
            </div>
          )}
        </div>
      </Sidebar>

      <main className={styles.main}>
        <div className={styles.welcome}>
          <h2 className={styles.welcomeTitle}>Welcome to Team Agent</h2>
          <p className={styles.welcomeText}>Select a room to start chatting.</p>
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
