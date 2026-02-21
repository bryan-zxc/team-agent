"use client";

import { useState } from "react";
import styles from "./MemberProfileEditor.module.css";

type MemberProfileEditorProps = {
  content: string;
  onSave: (content: string) => void;
  onCancel: () => void;
};

export function MemberProfileEditor({ content, onSave, onCancel }: MemberProfileEditorProps) {
  const [draft, setDraft] = useState(content);

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <h2 className={styles.title}>Edit Profile</h2>
        <div className={styles.actions}>
          <button className={styles.cancelBtn} onClick={onCancel}>Cancel</button>
          <button className={styles.saveBtn} onClick={() => onSave(draft)}>Save</button>
        </div>
      </div>
      <textarea
        className={styles.editor}
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        spellCheck={false}
      />
    </div>
  );
}
