"use client";

import { useRouter } from "next/navigation";
import clsx from "clsx";
import type { Member } from "@/types";
import styles from "./MemberList.module.css";

type MemberListProps = {
  members: Member[];
  onAddClick: () => void;
};

export function MemberList({ members, onAddClick }: MemberListProps) {
  const router = useRouter();

  return (
    <div className={styles.container}>
      <div className={styles.sectionLabel}>Members</div>
      <div className={styles.list}>
        {members.map((member) => (
          <button
            key={member.id}
            className={clsx(styles.memberItem, member.type === "ai" && styles.memberItemClickable)}
            onClick={() => member.type === "ai" && router.push(`/members/${member.id}`)}
          >
            <div className={clsx(styles.avatar, member.type === "ai" ? styles.avatarAi : styles.avatarHuman)}>
              {member.display_name[0]}
            </div>
            <div className={styles.memberInfo}>
              <span className={styles.memberName}>{member.display_name}</span>
            </div>
            <span className={clsx(styles.typeBadge, member.type === "ai" && styles.typeBadgeAi)}>
              {member.type === "ai" ? "AI" : "Human"}
            </span>
          </button>
        ))}
      </div>
      <button className={styles.addButton} onClick={onAddClick}>
        + Add Member
      </button>
    </div>
  );
}
