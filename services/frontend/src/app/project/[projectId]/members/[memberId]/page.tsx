"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { Sidebar } from "@/components/sidebar/Sidebar";
import { AddMemberModal } from "@/components/members/AddMemberModal";
import { MemberProfile } from "@/components/members/MemberProfile";
import { MemberProfileEditor } from "@/components/members/MemberProfileEditor";
import type { Member, Room } from "@/types";
import styles from "./page.module.css";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function MemberProfilePage() {
  const params = useParams<{ projectId: string; memberId: string }>();
  const router = useRouter();

  const [rooms, setRooms] = useState<Room[]>([]);
  const [members, setMembers] = useState<Member[]>([]);
  const [profileContent, setProfileContent] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [showAddModal, setShowAddModal] = useState(false);

  const member = members.find((m) => m.id === params.memberId);

  useEffect(() => {
    if (!params.projectId) return;
    fetch(`${API_URL}/projects/${params.projectId}/rooms`).then((r) => r.json()).then(setRooms);
    fetch(`${API_URL}/projects/${params.projectId}/members`).then((r) => r.json()).then(setMembers);
  }, [params.projectId]);

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
      <Sidebar
        rooms={rooms}
        members={members}
        onRoomClick={(roomId) => router.push(`/project/${params.projectId}/chat/${roomId}`)}
        onAddMember={() => setShowAddModal(true)}
        onMemberClick={(id) => router.push(`/project/${params.projectId}/members/${id}`)}
      />

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
        projectId={params.projectId}
        onClose={() => setShowAddModal(false)}
        onMemberAdded={handleMemberAdded}
      />
    </div>
  );
}
