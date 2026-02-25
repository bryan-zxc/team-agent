import clsx from "clsx";
import { motion } from "motion/react";
import type { Member } from "@/types";
import styles from "./MentionDropdown.module.css";

type MentionDropdownProps = {
  members: Member[];
  query: string;
  selectedIndex: number;
  onSelect: (member: Member) => void;
};

export function MentionDropdown({ members, query, selectedIndex, onSelect }: MentionDropdownProps) {
  const queryLower = query.toLowerCase();

  const filtered = members.filter((m) => {
    const name = m.display_name.toLowerCase();
    return queryLower === "" || name.startsWith(queryLower) || name.includes(queryLower);
  });

  // Sort: startsWith matches first, then includes matches
  filtered.sort((a, b) => {
    const aStarts = a.display_name.toLowerCase().startsWith(queryLower);
    const bStarts = b.display_name.toLowerCase().startsWith(queryLower);
    if (aStarts && !bStarts) return -1;
    if (!aStarts && bStarts) return 1;
    return 0;
  });

  if (filtered.length === 0) return null;

  return (
    <motion.div
      className={styles.dropdown}
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: 4 }}
      transition={{ duration: 0.15 }}
    >
      {filtered.map((member, i) => {
        const isAi = member.type === "ai" || member.type === "coordinator";
        return (
          <button
            key={member.id}
            className={clsx(styles.item, i === selectedIndex && styles.active)}
            onMouseDown={(e) => {
              e.preventDefault(); // prevent textarea blur
              onSelect(member);
            }}
          >
            <div className={clsx(styles.avatar, isAi ? styles.avatarAi : styles.avatarHuman)}>
              {member.display_name[0]}
            </div>
            <span className={styles.name}>{member.display_name}</span>
            {isAi && <span className={styles.badge}>AI</span>}
          </button>
        );
      })}
    </motion.div>
  );
}

/** Return the filtered member list for external keyboard navigation. */
export function filterMembers(members: Member[], query: string): Member[] {
  const queryLower = query.toLowerCase();
  const filtered = members.filter((m) => {
    const name = m.display_name.toLowerCase();
    return queryLower === "" || name.startsWith(queryLower) || name.includes(queryLower);
  });
  filtered.sort((a, b) => {
    const aStarts = a.display_name.toLowerCase().startsWith(queryLower);
    const bStarts = b.display_name.toLowerCase().startsWith(queryLower);
    if (aStarts && !bStarts) return -1;
    if (!aStarts && bStarts) return 1;
    return 0;
  });
  return filtered;
}
