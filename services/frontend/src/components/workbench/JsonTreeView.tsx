"use client";

import { useState } from "react";
import styles from "./JsonTreeView.module.css";

function JsonNode({
  value,
  label,
  defaultExpanded = false,
  depth = 0,
}: {
  value: unknown;
  label?: string;
  defaultExpanded?: boolean;
  depth?: number;
}) {
  const [expanded, setExpanded] = useState(defaultExpanded);

  const indent = { paddingLeft: depth * 16 };

  const labelEl = label !== undefined && (
    <>
      <span className={styles.key}>{label}</span>
      <span className={styles.colon}>:</span>
    </>
  );

  if (value === null) {
    return (
      <div className={styles.row} style={indent}>
        <span className={styles.toggleSpacer} />
        {labelEl}
        <span className={styles.null}>null</span>
      </div>
    );
  }

  if (typeof value === "string") {
    return (
      <div className={styles.row} style={indent}>
        <span className={styles.toggleSpacer} />
        {labelEl}
        <span className={styles.string}>&quot;{value}&quot;</span>
      </div>
    );
  }

  if (typeof value === "number") {
    return (
      <div className={styles.row} style={indent}>
        <span className={styles.toggleSpacer} />
        {labelEl}
        <span className={styles.number}>{String(value)}</span>
      </div>
    );
  }

  if (typeof value === "boolean") {
    return (
      <div className={styles.row} style={indent}>
        <span className={styles.toggleSpacer} />
        {labelEl}
        <span className={styles.boolean}>{String(value)}</span>
      </div>
    );
  }

  if (Array.isArray(value)) {
    const items = value;
    return (
      <div>
        <div className={styles.row} style={indent}>
          <button className={styles.toggle} onClick={() => setExpanded(!expanded)}>
            {expanded ? "▾" : "▸"}
          </button>
          {labelEl}
          <span className={styles.bracket}>[</span>
          {!expanded && (
            <>
              <span className={styles.count}>{items.length} {items.length === 1 ? "item" : "items"}</span>
              <span className={styles.bracket}>]</span>
            </>
          )}
        </div>
        {expanded && (
          <>
            {items.map((item, i) => (
              <JsonNode key={i} value={item} label={String(i)} depth={depth + 1} />
            ))}
            <div className={styles.row} style={indent}>
              <span className={styles.toggleSpacer} />
              <span className={styles.bracket}>]</span>
            </div>
          </>
        )}
      </div>
    );
  }

  if (typeof value === "object") {
    const entries = Object.entries(value as Record<string, unknown>);
    return (
      <div>
        <div className={styles.row} style={indent}>
          <button className={styles.toggle} onClick={() => setExpanded(!expanded)}>
            {expanded ? "▾" : "▸"}
          </button>
          {labelEl}
          <span className={styles.bracket}>{"{"}</span>
          {!expanded && (
            <>
              <span className={styles.count}>{entries.length} {entries.length === 1 ? "key" : "keys"}</span>
              <span className={styles.bracket}>{"}"}</span>
            </>
          )}
        </div>
        {expanded && (
          <>
            {entries.map(([k, v]) => (
              <JsonNode key={k} value={v} label={k} depth={depth + 1} />
            ))}
            <div className={styles.row} style={indent}>
              <span className={styles.toggleSpacer} />
              <span className={styles.bracket}>{"}"}</span>
            </div>
          </>
        )}
      </div>
    );
  }

  return (
    <div className={styles.row} style={indent}>
      <span className={styles.toggleSpacer} />
      {labelEl}
      <span>{String(value)}</span>
    </div>
  );
}

export function JsonTreeView({ data }: { data: string }) {
  let parsed: unknown;
  try {
    parsed = JSON.parse(data);
  } catch {
    return (
      <div className={styles.container}>
        <div className={styles.error}>
          <div className={styles.errorLabel}>Invalid JSON</div>
          <div className={styles.errorRaw}>{data}</div>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.container}>
      <JsonNode value={parsed} defaultExpanded />
    </div>
  );
}
