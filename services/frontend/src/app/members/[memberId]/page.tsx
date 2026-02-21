"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useTheme } from "@/hooks/useTheme";
import { MemberList } from "@/components/members/MemberList";
import { AddMemberModal } from "@/components/members/AddMemberModal";
import { MemberProfile } from "@/components/members/MemberProfile";
import { MemberProfileEditor } from "@/components/members/MemberProfileEditor";
import type { Member, Room } from "@/types";
import styles from "./page.module.css";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function MemberProfilePage() {
  const params = useParams<{ memberId: string }>();
  const router = useRouter();
  const { theme, toggle } = useTheme();

  const [rooms, setRooms] = useState<Room[]>([]);
  const [members, setMembers] = useState<Member[]>([]);
  const [profileContent, setProfileContent] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [showAddModal, setShowAddModal] = useState(false);

  const member = members.find((m) => m.id === params.memberId);

  useEffect(() => {
    fetch(`${API_URL}/rooms`).then((r) => r.json()).then(setRooms);
    fetch(`${API_URL}/members`).then((r) => r.json()).then(setMembers);
  }, []);

  useEffect(() => {
    if (!params.memberId) return;
    fetch(`${API_URL}/members/${params.memberId}/profile`)
      .then((r) => r.json())
      .then((data) => setProfileContent(data.content))
      .catch(() => setProfileContent(null));
  }, [params.memberId]);

  const handleSave = useCallback(async (content: string) => {
    await fetch(`${API_URL}/members/${params.memberId}/profile`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content }),
    });
    setProfileContent(content);
    setEditing(false);
  }, [params.memberId]);

  const handleMemberAdded = useCallback((newMember: Member) => {
    setMembers((prev) => [...prev, newMember]);
  }, []);

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
          {rooms.map((r) => (
            <button
              key={r.id}
              className={styles.roomItem}
              onClick={() => router.push(`/chat/${r.id}`)}
            >
              <div className={styles.roomIcon}>#</div>
              <div className={styles.roomInfo}>
                <div className={styles.roomName}>{r.name}</div>
              </div>
            </button>
          ))}
        </div>

        <MemberList
          members={members}
          onAddClick={() => setShowAddModal(true)}
        />
      </aside>

      <main className={styles.main}>
        {profileContent !== null && member ? (
          editing ? (
            <MemberProfileEditor
              content={profileContent}
              onSave={handleSave}
              onCancel={() => setEditing(false)}
            />
          ) : (
            <MemberProfile
              name={member.display_name}
              content={profileContent}
              onEdit={() => setEditing(true)}
            />
          )
        ) : (
          <div className={styles.loading}>Loading profile...</div>
        )}
      </main>

      <AddMemberModal
        open={showAddModal}
        onClose={() => setShowAddModal(false)}
        onMemberAdded={handleMemberAdded}
      />
    </div>
  );
}
