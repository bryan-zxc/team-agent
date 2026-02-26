import clsx from "clsx";
import { motion } from "motion/react";
import type { Skill } from "@/types";
import styles from "./SlashCommandDropdown.module.css";

type SlashCommandDropdownProps = {
  skills: Skill[];
  query: string;
  selectedIndex: number;
  onSelect: (skill: Skill) => void;
};

export function SlashCommandDropdown({
  skills,
  query,
  selectedIndex,
  onSelect,
}: SlashCommandDropdownProps) {
  if (skills.length === 0) return null;

  return (
    <motion.div
      className={styles.dropdown}
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: 4 }}
      transition={{ duration: 0.15 }}
    >
      {skills.map((skill, i) => (
        <button
          key={skill.path}
          className={clsx(styles.item, i === selectedIndex && styles.active)}
          onMouseDown={(e) => {
            e.preventDefault();
            onSelect(skill);
          }}
        >
          <span className={styles.command}>/{skill.name}</span>
          <span className={styles.description}>{skill.description}</span>
        </button>
      ))}
    </motion.div>
  );
}

export function filterSkills(skills: Skill[], query: string): Skill[] {
  const q = query.toLowerCase();
  const filtered = skills.filter((s) => {
    const name = s.name.toLowerCase();
    return q === "" || name.startsWith(q) || name.includes(q);
  });
  filtered.sort((a, b) => {
    const aStarts = a.name.toLowerCase().startsWith(q);
    const bStarts = b.name.toLowerCase().startsWith(q);
    if (aStarts && !bStarts) return -1;
    if (!aStarts && bStarts) return 1;
    return 0;
  });
  return filtered;
}
