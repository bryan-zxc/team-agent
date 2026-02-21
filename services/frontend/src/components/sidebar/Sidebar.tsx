"use client";

import clsx from "clsx";
import { useTheme } from "@/hooks/useTheme";
import { MemberList } from "@/components/members/MemberList";
import type { Member, Room } from "@/types";
import styles from "./Sidebar.module.css";

type SidebarProps = {
  rooms: Room[];
  members: Member[];
  activeRoomId?: string;
  onRoomClick: (roomId: string) => void;
  onAddMember: () => void;
  onMemberClick?: (memberId: string) => void;
  roomActions?: React.ReactNode;
  children?: React.ReactNode;
};

export function Sidebar({
  rooms,
  members,
  activeRoomId,
  onRoomClick,
  onAddMember,
  onMemberClick,
  roomActions,
  children,
}: SidebarProps) {
  const { theme, toggle } = useTheme();

  return (
    <aside className={styles.sidebar}>
      <header className={styles.sidebarHeader}>
        <div className={styles.logo}>
          <div className={styles.logoMark}>ta</div>
          <h1 className={styles.logoText}>Team Agent</h1>
        </div>
        <button className={styles.themeToggle} onClick={toggle} aria-label="Toggle theme">
          {theme === "light" ? "\u263D" : "\u2600"}
        </button>
      </header>

      <div className={styles.sectionLabel}>Rooms</div>

      <nav className={clsx(styles.roomList, activeRoomId !== undefined && styles.roomListScrollable)}>
        {rooms.map((room) => (
          <button
            key={room.id}
            className={clsx(styles.roomItem, room.id === activeRoomId && styles.roomItemActive)}
            onClick={() => onRoomClick(room.id)}
          >
            <div className={clsx(styles.roomIcon, room.id === activeRoomId && styles.roomIconActive)}>
              #
            </div>
            <div className={styles.roomInfo}>
              <div className={styles.roomName}>{room.name}</div>
            </div>
          </button>
        ))}
      </nav>

      {roomActions}

      <MemberList
        members={members}
        onAddClick={onAddMember}
        onMemberClick={onMemberClick}
      />

      {children}
    </aside>
  );
}
