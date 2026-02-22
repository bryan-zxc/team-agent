"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import clsx from "clsx";
import { generateRoomName } from "@/lib/roomNames";
import type { Member, Room } from "@/types";
import styles from "./ChatSidePanel.module.css";

type ChatSidePanelProps = {
  rooms: Room[];
  activeRoomId?: string;
  onRoomClick: (roomId: string) => void;
  onCreateRoom?: (name: string) => void;
  onRenameRoom?: (roomId: string, newName: string) => void;
  currentMember?: Member | null;
};

export function ChatSidePanel({
  rooms,
  activeRoomId,
  onRoomClick,
  onCreateRoom,
  onRenameRoom,
  currentMember,
}: ChatSidePanelProps) {
  const [creating, setCreating] = useState(false);
  const [createValue, setCreateValue] = useState("");
  const [placeholder, setPlaceholder] = useState("");
  const createInputRef = useRef<HTMLInputElement>(null);

  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const renameInputRef = useRef<HTMLInputElement>(null);
  const clickTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const startCreating = useCallback(() => {
    setPlaceholder(generateRoomName());
    setCreateValue("");
    setCreating(true);
  }, []);

  useEffect(() => {
    if (creating && createInputRef.current) {
      createInputRef.current.focus();
    }
  }, [creating]);

  useEffect(() => {
    if (renamingId && renameInputRef.current) {
      renameInputRef.current.focus();
      renameInputRef.current.select();
    }
  }, [renamingId]);

  const submitCreate = useCallback(() => {
    const name = createValue.trim() || placeholder;
    if (name && onCreateRoom) onCreateRoom(name);
    setCreating(false);
    setCreateValue("");
  }, [createValue, placeholder, onCreateRoom]);

  const cancelCreate = useCallback(() => {
    setCreating(false);
    setCreateValue("");
  }, []);

  const startRenaming = useCallback((room: Room) => {
    setRenamingId(room.id);
    setRenameValue(room.name);
  }, []);

  const submitRename = useCallback(() => {
    if (renamingId && renameValue.trim() && onRenameRoom) {
      onRenameRoom(renamingId, renameValue.trim());
    }
    setRenamingId(null);
    setRenameValue("");
  }, [renamingId, renameValue, onRenameRoom]);

  const cancelRename = useCallback(() => {
    setRenamingId(null);
    setRenameValue("");
  }, []);

  return (
    <div className={styles.panel}>
      <div className={styles.header}>
        <div className={styles.logo}>
          <div className={styles.logoMark}>ta</div>
          <span className={styles.logoText}>Team Agent</span>
        </div>
      </div>

      <div className={styles.sectionHeader}>
        <span className={styles.sectionLabel}>Rooms</span>
        {onCreateRoom && (
          <button
            className={clsx(styles.addRoomBtn, creating && styles.addRoomBtnActive)}
            onClick={startCreating}
            aria-label="Create room"
          >
            +
          </button>
        )}
      </div>

      <nav className={styles.roomList}>
        {rooms.map((room) => (
          <button
            key={room.id}
            className={clsx(styles.roomItem, room.id === activeRoomId && styles.roomItemActive)}
            onClick={() => {
              if (renamingId === room.id) return;
              if (clickTimer.current) clearTimeout(clickTimer.current);
              clickTimer.current = setTimeout(() => {
                clickTimer.current = null;
                onRoomClick(room.id);
              }, 250);
            }}
            onDoubleClick={(e) => {
              e.preventDefault();
              if (clickTimer.current) {
                clearTimeout(clickTimer.current);
                clickTimer.current = null;
              }
              if (onRenameRoom) startRenaming(room);
            }}
          >
            <div className={clsx(styles.roomIcon, room.id === activeRoomId && styles.roomIconActive)}>
              #
            </div>
            <div className={styles.roomInfo}>
              {renamingId === room.id ? (
                <input
                  ref={renameInputRef}
                  className={styles.renameInput}
                  value={renameValue}
                  onChange={(e) => setRenameValue(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") submitRename();
                    if (e.key === "Escape") cancelRename();
                  }}
                  onBlur={submitRename}
                  onClick={(e) => e.stopPropagation()}
                />
              ) : (
                <div className={styles.roomName}>{room.name}</div>
              )}
            </div>
          </button>
        ))}

        {creating && (
          <div className={styles.roomCreateInline}>
            <div className={clsx(styles.roomIcon, styles.roomIconActive)}>#</div>
            <input
              ref={createInputRef}
              className={styles.createInput}
              placeholder={placeholder}
              value={createValue}
              onChange={(e) => setCreateValue(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") submitCreate();
                if (e.key === "Escape") cancelCreate();
              }}
              onBlur={cancelCreate}
            />
          </div>
        )}
      </nav>

      {creating && <div className={styles.hint}>Enter to create · Esc to cancel</div>}
      {renamingId && <div className={styles.hint}>Enter to save · Esc to cancel</div>}

      {currentMember && (
        <div className={styles.footer}>
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
    </div>
  );
}
