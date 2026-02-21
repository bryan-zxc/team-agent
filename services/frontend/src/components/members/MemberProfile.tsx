"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import styles from "./MemberProfile.module.css";

type MemberProfileProps = {
  name: string;
  content: string;
  onEdit: () => void;
};

export function MemberProfile({ name, content, onEdit }: MemberProfileProps) {
  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <div className={styles.nameRow}>
          <h2 className={styles.name}>{name}</h2>
          <span className={styles.lockIcon} title="Name cannot be changed">&#x1F512;</span>
        </div>
        <button className={styles.editBtn} onClick={onEdit}>Edit</button>
      </div>
      <div className={styles.markdown}>
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
      </div>
    </div>
  );
}
