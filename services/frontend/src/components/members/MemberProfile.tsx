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
          <span className={styles.lockIcon} title="Name cannot be changed">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
            <path d="M7 11V7a5 5 0 0 1 10 0v4" />
          </svg>
        </span>
        </div>
        <button className={styles.editBtn} onClick={onEdit}>Edit</button>
      </div>
      <div className={styles.markdown}>
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
      </div>
    </div>
  );
}
