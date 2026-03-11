"use client";

import { useState, useCallback } from "react";
import styles from "./CostCard.module.css";

type CostCardProps = {
  totalCost: number;
  middleStat: { label: string; value: string };
  marginPercent: number;
  onMarginChange: (margin: number) => void;
};

function formatCurrency(value: number): string {
  if (value >= 1000) return `$${(value / 1000).toFixed(1)}k`;
  if (value >= 1) return `$${value.toFixed(2)}`;
  return `$${value.toFixed(4)}`;
}

export function CostCard({
  totalCost,
  middleStat,
  marginPercent,
  onMarginChange,
}: CostCardProps) {
  const [marginDraft, setMarginDraft] = useState(String(marginPercent));
  const nsr = totalCost * (1 + marginPercent / 100);

  const handleMarginBlur = useCallback(() => {
    const parsed = parseFloat(marginDraft);
    if (!isNaN(parsed) && parsed >= 0 && parsed !== marginPercent) {
      onMarginChange(parsed);
    } else {
      setMarginDraft(String(marginPercent));
    }
  }, [marginDraft, marginPercent, onMarginChange]);

  const handleMarginKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === "Enter") {
        (e.target as HTMLInputElement).blur();
      }
    },
    [],
  );

  return (
    <div className={styles.card}>
      <div className={styles.hero}>
        <div className={styles.heroLabel}>NSR</div>
        <div className={styles.heroValue}>{formatCurrency(nsr)}</div>
      </div>
      <div className={styles.stats}>
        <div className={styles.stat}>
          <div className={styles.statLabel}>API Cost</div>
          <div className={styles.statValue}>{formatCurrency(totalCost)}</div>
        </div>
        <div className={styles.stat}>
          <div className={styles.statLabel}>{middleStat.label}</div>
          <div className={styles.statValue}>{middleStat.value}</div>
        </div>
        <div className={styles.stat}>
          <div className={styles.statLabel}>Margin</div>
          <div className={styles.statValue}>
            <input
              className={styles.marginInput}
              type="text"
              inputMode="decimal"
              value={marginDraft}
              onChange={(e) => setMarginDraft(e.target.value)}
              onBlur={handleMarginBlur}
              onKeyDown={handleMarginKeyDown}
              aria-label="Margin percentage"
            />
            <span className={styles.marginSuffix}>%</span>
          </div>
        </div>
      </div>
    </div>
  );
}
