"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useTheme } from "@/hooks/useTheme";
import type { Room, User } from "@/types";
import styles from "./page.module.css";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function Home() {
  const router = useRouter();
  const { theme, toggle } = useTheme();
  const [rooms, setRooms] = useState<Room[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [selectedUser, setSelectedUser] = useState<string | null>(null);
  const [newRoomName, setNewRoomName] = useState("");
  const [showUserPicker, setShowUserPicker] = useState(false);

  useEffect(() => {
    fetch(`${API_URL}/rooms`).then((r) => r.json()).then(setRooms);
    fetch(`${API_URL}/users`).then((r) => r.json()).then(setUsers);
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
      <aside className={styles.sidebar}>
        <div className={styles.sidebarHeader}>
          <div className={styles.logo}>
            <div className={styles.logoMark}>ta</div>
            <h1 className={styles.logoText}>Team Agent</h1>
          </div>
          <button className={styles.themeToggle} onClick={toggle} title="Toggle theme">
            {theme === "light" ? "\u263D" : "\u2600"}
          </button>
        </div>

        <div className={styles.sectionLabel}>Rooms</div>

        <div className={styles.roomList}>
          {rooms.map((room) => (
            <button
              key={room.id}
              className={styles.roomItem}
              onClick={() => openRoom(room.id)}
            >
              <div className={styles.roomIcon}>#</div>
              <div className={styles.roomInfo}>
                <div className={styles.roomName}>{room.name}</div>
              </div>
            </button>
          ))}
        </div>

        <div className={styles.newRoom}>
          <input
            className={styles.newRoomInput}
            placeholder="New room name..."
            value={newRoomName}
            onChange={(e) => setNewRoomName(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && createRoom()}
          />
          <button className={styles.newRoomBtn} onClick={createRoom}>+</button>
        </div>

        <div className={styles.sidebarFooter}>
          <button
            className={styles.userSelector}
            onClick={() => setShowUserPicker(!showUserPicker)}
          >
            {currentUser ? (
              <>
                <div className={`${styles.avatar} ${currentUser.type === "ai" ? styles.avatarAi : styles.avatarHuman}`}>
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
                  <div className={`${styles.avatar} ${styles.avatarHuman}`}>
                    {user.display_name[0]}
                  </div>
                  <span>{user.display_name}</span>
                </button>
              ))}
            </div>
          )}
        </div>
      </aside>

      <main className={styles.main}>
        <div className={styles.welcome}>
          <h2 className={styles.welcomeTitle}>Welcome to Team Agent</h2>
          <p className={styles.welcomeText}>Select a room to start chatting.</p>
        </div>
      </main>
    </div>
  );
}
