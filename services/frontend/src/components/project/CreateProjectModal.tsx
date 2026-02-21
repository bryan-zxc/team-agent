"use client";

import { useCallback, useState } from "react";
import { motion, AnimatePresence } from "motion/react";
import styles from "./CreateProjectModal.module.css";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type CreateProjectModalProps = {
  open: boolean;
  onClose: () => void;
  onCreated: (project: { id: string }) => void;
};

export function CreateProjectModal({ open, onClose, onCreated }: CreateProjectModalProps) {
  const [name, setName] = useState("");
  const [gitRepoUrl, setGitRepoUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = useCallback(async () => {
    if (!name.trim() || !gitRepoUrl.trim()) return;

    const userId = localStorage.getItem("user_id");
    if (!userId) {
      setError("Please select a user first");
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const res = await fetch(`${API_URL}/projects`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: name.trim(),
          git_repo_url: gitRepoUrl.trim(),
          creator_user_id: userId,
        }),
      });

      if (!res.ok) {
        const data = await res.json();
        setError(data.detail || "Failed to create project");
        return;
      }

      const project = await res.json();
      setName("");
      setGitRepoUrl("");
      onCreated(project);
      onClose();
    } catch {
      setError("Failed to create project");
    } finally {
      setLoading(false);
    }
  }, [name, gitRepoUrl, onCreated, onClose]);

  if (!open) return null;

  return (
    <AnimatePresence>
      <motion.div
        className={styles.overlay}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onClick={onClose}
      >
        <motion.div
          className={styles.modal}
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 12 }}
          transition={{ duration: 0.2 }}
          onClick={(e) => e.stopPropagation()}
        >
          <div className={styles.header}>
            <h3 className={styles.title}>Create Project</h3>
            <button className={styles.closeBtn} onClick={onClose} aria-label="Close">&times;</button>
          </div>

          <div className={styles.body}>
            <div className={styles.field}>
              <label className={styles.label}>Project name</label>
              <input
                className={styles.input}
                placeholder="my-project"
                value={name}
                onChange={(e) => setName(e.target.value)}
                disabled={loading}
              />
            </div>

            <div className={styles.field}>
              <label className={styles.label}>Git repository URL</label>
              <input
                className={styles.input}
                placeholder="https://github.com/org/repo.git"
                value={gitRepoUrl}
                onChange={(e) => setGitRepoUrl(e.target.value)}
                disabled={loading}
              />
            </div>

            <button
              className={styles.submitBtn}
              onClick={handleSubmit}
              disabled={loading || !name.trim() || !gitRepoUrl.trim()}
            >
              {loading ? <span className={styles.spinner} /> : "Create"}
            </button>

            {error && <p className={styles.error}>{error}</p>}
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}
