"use client";

import { useCallback, useState } from "react";
import clsx from "clsx";
import { apiFetch } from "@/lib/api";
import styles from "./ModeToggleStrip.module.css";

type Props = {
  workloadId: string;
  permissionMode: "default" | "acceptEdits";
  disabled?: boolean;
};

export function ModeToggleStrip({ workloadId, permissionMode, disabled }: Props) {
  const [confirming, setConfirming] = useState(false);
  const [switching, setSwitching] = useState(false);

  const isVibe = permissionMode === "acceptEdits";
  const targetMode = isVibe ? "default" : "acceptEdits";

  const handleToggleClick = useCallback(() => {
    if (disabled || switching) return;
    setConfirming(true);
  }, [disabled, switching]);

  const handleCancel = useCallback(() => {
    setConfirming(false);
  }, []);

  const handleConfirm = useCallback(async () => {
    setSwitching(true);
    setConfirming(false);
    try {
      await apiFetch(`/workloads/${workloadId}/switch-mode`, {
        method: "POST",
        body: JSON.stringify({ permission_mode: targetMode }),
      });
    } finally {
      setSwitching(false);
    }
  }, [workloadId, targetMode]);

  return (
    <>
      <div className={clsx(styles.strip, isVibe && styles.stripVibe, disabled && styles.stripDisabled)}>
        {isVibe && (
          <svg className={styles.zapIcon} width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
          </svg>
        )}
        <span className={clsx(styles.label, isVibe && styles.labelVibe)}>
          {isVibe ? "Vibe coding" : "Standard mode"}
        </span>
        <button
          className={clsx(styles.toggle, isVibe && styles.toggleOn)}
          onClick={handleToggleClick}
          disabled={disabled || switching}
          aria-label={`Switch to ${isVibe ? "standard" : "vibe coding"} mode`}
        />
        <span className={clsx(styles.desc, isVibe && styles.descVibe)}>
          {switching
            ? "Switching..."
            : isVibe
              ? "All file edits auto-accepted"
              : "File edits require approval"}
        </span>
      </div>

      {confirming && (
        <div className={styles.overlay} onClick={handleCancel}>
          <div className={styles.dialog} onClick={(e) => e.stopPropagation()}>
            <h3 className={styles.dialogTitle}>
              {isVibe ? "Switch to standard mode?" : "Switch to vibe coding?"}
            </h3>
            <p className={styles.dialogDesc}>
              {isVibe
                ? "File edits will require your approval before being applied."
                : "All file edits will be auto-accepted without approval prompts."}
            </p>
            <div className={styles.warning}>
              <svg className={styles.warningIcon} width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
                <line x1="12" y1="9" x2="12" y2="13" />
                <line x1="12" y1="17" x2="12.01" y2="17" />
              </svg>
              <span>This will stop the current session and restart with new permissions. The conversation is preserved.</span>
            </div>
            <div className={styles.dialogActions}>
              <button className={styles.btnCancel} onClick={handleCancel}>
                Cancel
              </button>
              <button
                className={clsx(styles.btnConfirm, isVibe ? styles.btnStandard : styles.btnVibe)}
                onClick={handleConfirm}
              >
                {isVibe ? "Switch to standard" : "Switch to vibe coding"}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
