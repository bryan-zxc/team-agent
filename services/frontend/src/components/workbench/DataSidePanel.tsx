"use client";

import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import styles from "./DataSidePanel.module.css";

type TableInfo = {
  name: string;
  column_count: number;
};

type DatabaseInfo = {
  name: string;
  tables: TableInfo[];
};

type DataSidePanelProps = {
  projectId: string;
  onOpenTable: (database: string, tableName: string) => void;
  onOpenSqlTab: (database: string) => void;
};

export function DataSidePanel({ projectId, onOpenTable, onOpenSqlTab }: DataSidePanelProps) {
  const [databases, setDatabases] = useState<DatabaseInfo[]>([]);
  const [expanded, setExpanded] = useState<Set<string>>(new Set(["data"]));
  const [loading, setLoading] = useState(true);

  const fetchTables = useCallback(async () => {
    setLoading(true);
    try {
      const res = await apiFetch(`/projects/${projectId}/data/tables`);
      if (res.ok) {
        setDatabases(await res.json());
      }
    } catch {
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    fetchTables();
  }, [fetchTables]);

  const toggleExpand = (dbName: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(dbName)) next.delete(dbName);
      else next.add(dbName);
      return next;
    });
  };

  const handleTableClick = (dbName: string, tableName: string) => {
    onOpenTable(dbName, tableName);
  };

  const handleNewQuery = () => {
    onOpenSqlTab("data");
  };

  return (
    <div className={styles.panel}>
      <div className={styles.header}>
        <div className={styles.logo}>
          <div className={styles.logoMark}>ta</div>
          <span className={styles.logoText}>Team Agent</span>
        </div>
      </div>

      <div className={styles.sectionHeader}>
        <span className={styles.sectionLabel}>Data</span>
        <button
          className={styles.newQueryBtn}
          onClick={handleNewQuery}
          aria-label="New query"
        >
          <svg
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
            <polyline points="14 2 14 8 20 8" />
          </svg>
          <span>New query</span>
        </button>
      </div>

      <div className={styles.list}>
        {loading && databases.length === 0 && (
          <div className={styles.emptyState}>Loading...</div>
        )}
        {!loading && databases.length === 0 && (
          <div className={styles.emptyState}>No databases</div>
        )}
        {databases.map((db) => (
          <div key={db.name}>
            <div
              className={styles.dbItem}
              onClick={() => toggleExpand(db.name)}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") toggleExpand(db.name);
              }}
            >
              <svg
                className={styles.chevron}
                width="12"
                height="12"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                style={{
                  transform: expanded.has(db.name)
                    ? "rotate(90deg)"
                    : "rotate(0deg)",
                }}
              >
                <polyline points="9 18 15 12 9 6" />
              </svg>
              <svg
                className={styles.dbIcon}
                width="14"
                height="14"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.8"
              >
                <ellipse cx="12" cy="5" rx="9" ry="3" />
                <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3" />
                <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5" />
              </svg>
              <span className={styles.dbLabel}>{db.name}</span>
              <span className={styles.tableCount}>{db.tables.length}</span>
            </div>
            {expanded.has(db.name) &&
              db.tables.map((table) => (
                <div
                  key={table.name}
                  className={styles.tableItem}
                  onClick={() => handleTableClick(db.name, table.name)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ")
                      handleTableClick(db.name, table.name);
                  }}
                  title={`${table.column_count} columns`}
                >
                  <svg
                    className={styles.tableIcon}
                    width="13"
                    height="13"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.8"
                  >
                    <rect x="3" y="3" width="18" height="18" rx="2" />
                    <line x1="3" y1="9" x2="21" y2="9" />
                    <line x1="9" y1="3" x2="9" y2="21" />
                  </svg>
                  <span className={styles.tableName}>{table.name}</span>
                </div>
              ))}
          </div>
        ))}
      </div>

      <button
        className={styles.refreshBtn}
        onClick={fetchTables}
        aria-label="Refresh"
        title="Refresh"
      >
        <svg
          width="14"
          height="14"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.8"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <polyline points="23 4 23 10 17 10" />
          <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
        </svg>
      </button>
    </div>
  );
}
