import styles from "./TimeCards.module.css";

type TimeCardsProps = {
  todayMinutes: number;
  weekMinutes: number;
  lifetimeMinutes: number;
};

function formatDuration(minutes: number): { number: string; unit: string } {
  if (minutes < 60) {
    return { number: String(minutes), unit: "m" };
  }
  const hours = Math.floor(minutes / 60);
  const remaining = minutes % 60;
  if (hours < 10) {
    return remaining > 0
      ? { number: `${hours}`, unit: `h ${remaining}m` }
      : { number: String(hours), unit: "h" };
  }
  return { number: String(Math.round(minutes / 60)), unit: "h" };
}

export function TimeCards({
  todayMinutes,
  weekMinutes,
  lifetimeMinutes,
}: TimeCardsProps) {
  const today = formatDuration(todayMinutes);
  const week = formatDuration(weekMinutes);
  const lifetime = formatDuration(lifetimeMinutes);

  return (
    <>
      <div className={styles.cards}>
        <div className={styles.card}>
          <div className={styles.label}>Today</div>
          <div className={styles.value}>
            {today.number}
            <span className={styles.unit}>{today.unit}</span>
          </div>
        </div>
        <div className={styles.card}>
          <div className={styles.label}>This Week</div>
          <div className={styles.value}>
            {week.number}
            <span className={styles.unit}>{week.unit}</span>
          </div>
        </div>
        <div className={styles.card}>
          <div className={styles.label}>Lifetime</div>
          <div className={styles.value}>
            {lifetime.number}
            <span className={styles.unit}>{lifetime.unit}</span>
          </div>
        </div>
      </div>
      <div className={styles.annotation}>
        <span className={styles.dot} />
        Tracking active
      </div>
    </>
  );
}
