"use client";

import { useCallback, useEffect, useState } from "react";
import clsx from "clsx";
import { apiFetch } from "@/lib/api";
import type { DispatchCardBlock, DispatchWorkloadItem } from "@/types";
import styles from "./DispatchCard.module.css";

type ItemState = DispatchWorkloadItem & { removed: boolean };
type CardState = "pending" | "dispatched" | "cancelled";

type Props = {
  block: DispatchCardBlock;
  hasWorkloads?: boolean;
  onDispatched?: () => void;
};

export function DispatchCard({ block, hasWorkloads, onDispatched }: Props) {
  const [state, setState] = useState<CardState>(
    hasWorkloads ? "dispatched" : "pending",
  );
  const [items, setItems] = useState<ItemState[]>(() =>
    block.workloads.map((w) => ({ ...w, permission_mode: w.permission_mode ?? "default", removed: false })),
  );
  const [submitting, setSubmitting] = useState(false);

  // If workloads appear after dispatch, mark card as dispatched
  useEffect(() => {
    if (hasWorkloads && state === "pending") {
      setState("dispatched");
    }
  }, [hasWorkloads, state]);

  const toggleMode = useCallback((index: number) => {
    setItems((prev) =>
      prev.map((item, i) =>
        i === index
          ? {
              ...item,
              permission_mode:
                item.permission_mode === "default" ? "acceptEdits" : "default",
            }
          : item,
      ),
    );
  }, []);

  const toggleRemoved = useCallback((index: number) => {
    setItems((prev) =>
      prev.map((item, i) =>
        i === index ? { ...item, removed: !item.removed } : item,
      ),
    );
  }, []);

  const activeItems = items.filter((i) => !i.removed);

  const handleStart = useCallback(async () => {
    if (activeItems.length === 0) return;
    setSubmitting(true);
    try {
      const resp = await apiFetch("/workloads/dispatch", {
        method: "POST",
        body: JSON.stringify({
          chat_id: block.chat_id,
          dispatch_id: block.dispatch_id,
          workloads: activeItems.map(({ removed: _r, ...w }) => w),
        }),
      });
      if (!resp.ok) {
        setSubmitting(false);
        return;
      }
      setState("dispatched");
      onDispatched?.();
    } catch {
      setSubmitting(false);
    }
  }, [activeItems, block, onDispatched]);

  const handleCancel = useCallback(() => {
    setState("cancelled");
  }, []);

  // Resolved states — compact label
  if (state === "dispatched") {
    return (
      <div className={clsx(styles.card, styles.cardResolved)}>
        <div className={styles.resolvedLabel}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="20 6 9 17 4 12" />
          </svg>
          Workloads dispatched
        </div>
      </div>
    );
  }

  if (state === "cancelled") {
    return (
      <div className={clsx(styles.card, styles.cardResolved)}>
        <div className={styles.resolvedLabel}>Dispatch cancelled</div>
      </div>
    );
  }

  return (
    <div className={styles.card}>
      <div className={styles.header}>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
          <line x1="8" y1="6" x2="21" y2="6" />
          <line x1="8" y1="12" x2="21" y2="12" />
          <line x1="8" y1="18" x2="21" y2="18" />
          <line x1="3" y1="6" x2="3.01" y2="6" />
          <line x1="3" y1="12" x2="3.01" y2="12" />
          <line x1="3" y1="18" x2="3.01" y2="18" />
        </svg>
        Workloads to dispatch
      </div>

      <div className={styles.list}>
        {items.map((item, i) => (
          <div
            key={i}
            className={clsx(styles.item, item.removed && styles.itemRemoved)}
          >
            <div className={styles.itemAvatar}>{item.owner[0]}</div>
            <div className={styles.itemInfo}>
              <span className={styles.itemName}>{item.owner}</span>
              <span className={styles.itemTitle}>{item.title}</span>
            </div>

            {!item.removed && (
              <>
                <div className={styles.toggleWrap}>
                  {item.permission_mode === "acceptEdits" && (
                    <svg className={styles.zapIcon} width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
                    </svg>
                  )}
                  <span
                    className={clsx(
                      styles.toggleLabel,
                      item.permission_mode === "acceptEdits" && styles.toggleLabelVibe,
                    )}
                  >
                    {item.permission_mode === "acceptEdits" ? "Vibe" : "Standard"}
                  </span>
                  <button
                    className={clsx(
                      styles.toggle,
                      item.permission_mode === "acceptEdits" && styles.toggleOn,
                    )}
                    onClick={() => toggleMode(i)}
                    aria-label={`Toggle ${item.owner} to ${item.permission_mode === "default" ? "vibe" : "standard"} mode`}
                  />
                </div>
                <button
                  className={styles.removeBtn}
                  onClick={() => toggleRemoved(i)}
                  aria-label={`Remove ${item.owner}`}
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                    <line x1="18" y1="6" x2="6" y2="18" />
                    <line x1="6" y1="6" x2="18" y2="18" />
                  </svg>
                </button>
              </>
            )}

            {item.removed && (
              <button
                className={styles.undoBtn}
                onClick={() => toggleRemoved(i)}
              >
                Undo
              </button>
            )}
          </div>
        ))}
      </div>

      <div className={styles.footer}>
        <button
          className={styles.btnCancel}
          onClick={handleCancel}
          disabled={submitting}
        >
          Cancel
        </button>
        <button
          className={styles.btnStart}
          onClick={handleStart}
          disabled={submitting || activeItems.length === 0}
        >
          {submitting
            ? "Starting..."
            : activeItems.length === items.length
              ? "Start workloads"
              : `Start ${activeItems.length} workload${activeItems.length !== 1 ? "s" : ""}`}
        </button>
      </div>
    </div>
  );
}
