"use client";

import { useCallback, useEffect, useState } from "react";
import { motion, AnimatePresence } from "motion/react";
import type { AvailableUser, Member } from "@/types";
import styles from "./AddMemberModal.module.css";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type AddMemberModalProps = {
  open: boolean;
  onClose: () => void;
  onMemberAdded: (member: Member) => void;
};

type Tab = "human" | "ai";

export function AddMemberModal({ open, onClose, onMemberAdded }: AddMemberModalProps) {
  const [tab, setTab] = useState<Tab>("human");
  const [availableUsers, setAvailableUsers] = useState<AvailableUser[]>([]);
  const [agentName, setAgentName] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (open && tab === "human") {
      fetch(`${API_URL}/members/available-users`)
        .then((r) => r.json())
        .then(setAvailableUsers);
    }
  }, [open, tab]);

  const addHuman = useCallback(async (userId: string) => {
    setError(null);
    const res = await fetch(`${API_URL}/members/human`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: userId }),
    });
    if (!res.ok) {
      setError("Failed to add member");
      return;
    }
    const member: Member = await res.json();
    onMemberAdded(member);
    onClose();
  }, [onMemberAdded, onClose]);

  const generateAgent = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_URL}/members/ai`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: agentName.trim() || null }),
      });
      if (!res.ok) {
        const data = await res.json();
        setError(data.detail || "Agent generation failed");
        return;
      }
      const member: Member = await res.json();
      onMemberAdded(member);
      setAgentName("");
      onClose();
    } catch {
      setError("Agent generation failed");
    } finally {
      setLoading(false);
    }
  }, [agentName, onMemberAdded, onClose]);

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
            <h3 className={styles.title}>Add Member</h3>
            <button className={styles.closeBtn} onClick={onClose}>&times;</button>
          </div>

          <div className={styles.tabs}>
            <button
              className={`${styles.tab} ${tab === "human" ? styles.tabActive : ""}`}
              onClick={() => setTab("human")}
            >
              Human
            </button>
            <button
              className={`${styles.tab} ${tab === "ai" ? styles.tabActive : ""}`}
              onClick={() => setTab("ai")}
            >
              AI Agent
            </button>
          </div>

          <div className={styles.body}>
            {tab === "human" ? (
              <div className={styles.userList}>
                {availableUsers.length === 0 ? (
                  <p className={styles.empty}>No available users</p>
                ) : (
                  availableUsers.map((user) => (
                    <button
                      key={user.id}
                      className={styles.userOption}
                      onClick={() => addHuman(user.id)}
                    >
                      <div className={styles.userAvatar}>{user.display_name[0]}</div>
                      <span>{user.display_name}</span>
                    </button>
                  ))
                )}
              </div>
            ) : (
              <div className={styles.aiForm}>
                <label className={styles.label}>Name (optional)</label>
                <input
                  className={styles.input}
                  placeholder="Leave blank to auto-generate..."
                  value={agentName}
                  onChange={(e) => setAgentName(e.target.value)}
                  disabled={loading}
                />
                <button
                  className={styles.generateBtn}
                  onClick={generateAgent}
                  disabled={loading}
                >
                  {loading ? (
                    <span className={styles.spinner} />
                  ) : (
                    "Generate"
                  )}
                </button>
              </div>
            )}

            {error && <p className={styles.error}>{error}</p>}
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}
