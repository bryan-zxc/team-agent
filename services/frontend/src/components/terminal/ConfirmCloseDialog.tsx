"use client";

import { useState } from "react";
import styles from "./ConfirmCloseDialog.module.css";

type ConfirmCloseDialogProps = {
  onConfirm: () => void;
  onCancel: () => void;
};

export function ConfirmCloseDialog({ onConfirm, onCancel }: ConfirmCloseDialogProps) {
  const [dontAskAgain, setDontAskAgain] = useState(false);

  const handleConfirm = () => {
    if (dontAskAgain) {
      localStorage.setItem("terminal_close_no_confirm", "true");
    }
    onConfirm();
  };

  return (
    <div className={styles.overlay} onClick={onCancel}>
      <div className={styles.dialog} onClick={(e) => e.stopPropagation()}>
        <p className={styles.message}>
          Closing will terminate the terminal session. Continue?
        </p>
        <label className={styles.checkbox}>
          <input
            type="checkbox"
            checked={dontAskAgain}
            onChange={(e) => setDontAskAgain(e.target.checked)}
          />
          <span>Don&apos;t ask again</span>
        </label>
        <div className={styles.actions}>
          <button className={styles.cancelBtn} onClick={onCancel}>
            Cancel
          </button>
          <button className={styles.confirmBtn} onClick={handleConfirm}>
            Close terminal
          </button>
        </div>
      </div>
    </div>
  );
}
