"use client";

import { useState, useCallback } from "react";
import styles from "./HumanCostCard.module.css";

type HumanCostCardProps = {
  rate: number;
  totalHours: number;
  avgMarkupPercent: number;
  onRateChange: (rate: number) => void;
};

function formatCurrency(value: number): string {
  if (value >= 1000) return `$${(value / 1000).toFixed(1)}k`;
  if (value >= 1) return `$${value.toFixed(2)}`;
  return `$${value.toFixed(2)}`;
}

export function HumanCostCard({
  rate,
  totalHours,
  avgMarkupPercent,
  onRateChange,
}: HumanCostCardProps) {
  const [rateDraft, setRateDraft] = useState(String(rate));
  const nsr = rate * totalHours;

  const handleRateBlur = useCallback(() => {
    const parsed = parseFloat(rateDraft);
    if (!isNaN(parsed) && parsed >= 0 && parsed !== rate) {
      onRateChange(parsed);
    } else {
      setRateDraft(String(rate));
    }
  }, [rateDraft, rate, onRateChange]);

  const handleRateKeyDown = useCallback(
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
          <div className={styles.statLabel}>Rate</div>
          <div className={styles.statValue}>
            <span className={styles.ratePrefix}>$</span>
            <input
              className={styles.rateInput}
              type="text"
              inputMode="decimal"
              value={rateDraft}
              onChange={(e) => setRateDraft(e.target.value)}
              onBlur={handleRateBlur}
              onKeyDown={handleRateKeyDown}
              aria-label="Hourly rate"
            />
            <span className={styles.rateSuffix}>/hr</span>
          </div>
        </div>
        <div className={styles.stat}>
          <div className={styles.statLabel}>Hours</div>
          <div className={styles.statValue}>
            {totalHours.toFixed(1)}
            <span className={styles.unit}>h</span>
          </div>
        </div>
        <div className={styles.stat}>
          <div className={styles.statLabel}>Avg Markup</div>
          <div className={styles.statValue}>
            {avgMarkupPercent.toFixed(0)}
            <span className={styles.unit}>%</span>
          </div>
        </div>
      </div>
    </div>
  );
}
