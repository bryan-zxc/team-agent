"use client";

import { useMemo, useState } from "react";
import clsx from "clsx";
import type { WorkloadChat } from "@/types";
import styles from "./WorkloadPanel.module.css";

type WorkloadPanelProps = {
  workloads: WorkloadChat[];
  activeChatId: string;
  onSelectWorkload: (chatId: string) => void;
  onCancel: (workloadId: string) => void;
  onComplete: (workloadId: string) => void;
  onInterrupt: (workloadId: string) => void;
};

type StatusGroup = {
  key: string;
  label: string;
  colour: string;
  defaultExpanded: boolean;
  statuses: string[];
};

const GROUPS: StatusGroup[] = [
  {
    key: "attention",
    label: "Needs Attention",
    colour: "var(--warm)",
    defaultExpanded: true,
    statuses: ["needs_attention"],
  },
  {
    key: "progress",
    label: "In Progress",
    colour: "var(--accent)",
    defaultExpanded: true,
    statuses: ["assigned", "running"],
  },
  {
    key: "completed",
    label: "Completed",
    colour: "var(--text-muted)",
    defaultExpanded: false,
    statuses: ["completed"],
  },
  {
    key: "cancelled",
    label: "Cancelled",
    colour: "var(--text-muted)",
    defaultExpanded: false,
    statuses: ["cancelled"],
  },
];

const TERMINAL_STATUSES = new Set(["completed", "cancelled"]);

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const seconds = Math.floor(diff / 1000);
  if (seconds < 60) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

export function WorkloadPanel({
  workloads,
  activeChatId,
  onSelectWorkload,
  onCancel,
  onComplete,
  onInterrupt,
}: WorkloadPanelProps) {
  const [expanded, setExpanded] = useState<Record<string, boolean>>(() =>
    Object.fromEntries(GROUPS.map((g) => [g.key, g.defaultExpanded])),
  );

  const grouped = useMemo(() => {
    const result: Record<string, WorkloadChat[]> = {};
    for (const group of GROUPS) {
      result[group.key] = workloads.filter((w) =>
        group.statuses.includes(w.status),
      );
    }
    return result;
  }, [workloads]);

  const toggleGroup = (key: string) => {
    setExpanded((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  if (workloads.length === 0) {
    return (
      <div className={styles.panel}>
        <div className={styles.empty}>No workloads yet</div>
      </div>
    );
  }

  return (
    <div className={styles.panel}>
      {GROUPS.map((group) => {
        const items = grouped[group.key];
        if (items.length === 0) return null;

        const isExpanded = expanded[group.key];

        return (
          <div key={group.key} className={styles.section}>
            <button
              className={styles.sectionHeader}
              onClick={() => toggleGroup(group.key)}
            >
              <svg
                className={clsx(styles.chevron, isExpanded && styles.chevronOpen)}
                width="12"
                height="12"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <polyline points="9 18 15 12 9 6" />
              </svg>
              <span
                className={styles.sectionDot}
                style={{ background: group.colour }}
              />
              <span className={styles.sectionLabel}>{group.label}</span>
              <span className={styles.sectionCount}>{items.length}</span>
            </button>

            {isExpanded && (
              <div className={styles.cards}>
                {items.map((w) => (
                  <button
                    key={w.id}
                    className={clsx(
                      styles.card,
                      activeChatId === w.id && styles.cardActive,
                    )}
                    onClick={() => onSelectWorkload(w.id)}
                  >
                    <div className={styles.cardTitle}>{w.title}</div>
                    <div className={styles.cardMeta}>
                      {w.owner_name && (
                        <span className={styles.cardAgent}>{w.owner_name}</span>
                      )}
                      <span className={styles.cardTime}>
                        {timeAgo(w.updated_at)}
                      </span>
                    </div>
                    <div
                      className={styles.cardActions}
                      onClick={(e) => e.stopPropagation()}
                    >
                      {w.status === "needs_attention" && (
                        <button
                          className={styles.actionBtn}
                          onClick={() => onComplete(w.workload_id)}
                        >
                          Complete
                        </button>
                      )}
                      {(w.status === "running" || w.status === "assigned") && (
                        <button
                          className={styles.actionBtn}
                          onClick={() => onInterrupt(w.workload_id)}
                        >
                          Interrupt
                        </button>
                      )}
                      {!TERMINAL_STATUSES.has(w.status) && (
                        <button
                          className={clsx(styles.actionBtn, styles.actionCancel)}
                          onClick={() => onCancel(w.workload_id)}
                        >
                          Cancel
                        </button>
                      )}
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
