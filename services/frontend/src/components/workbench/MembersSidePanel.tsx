"use client";

import { MemberList } from "@/components/members/MemberList";
import type { Member } from "@/types";
import styles from "./MembersSidePanel.module.css";

type MembersSidePanelProps = {
  members: Member[];
  onAddMember: () => void;
  onMemberClick?: (memberId: string) => void;
};

export function MembersSidePanel({ members, onAddMember, onMemberClick }: MembersSidePanelProps) {
  return (
    <div className={styles.panel}>
      <div className={styles.header}>
        <span className={styles.headerLabel}>Members</span>
      </div>
      <div className={styles.content}>
        <MemberList
          members={members}
          onAddClick={onAddMember}
          onMemberClick={onMemberClick}
        />
      </div>
    </div>
  );
}
