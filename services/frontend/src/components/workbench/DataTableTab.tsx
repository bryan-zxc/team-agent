"use client";

import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { DataGrid, type SortState } from "./DataGrid";
import type { IDockviewPanelProps } from "dockview";
import styles from "./DataTableTab.module.css";

const DEFAULT_LIMIT = 100;

type DataTableTabParams = {
  projectId: string;
  database: string;
  tableName: string;
};

export function DataTableTab({ params }: IDockviewPanelProps<DataTableTabParams>) {
  const { projectId, database, tableName } = params;

  const [columns, setColumns] = useState<string[]>([]);
  const [rows, setRows] = useState<any[][]>([]);
  const [totalRows, setTotalRows] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sort, setSort] = useState<SortState>(null);

  const fetchData = useCallback(
    async (offset = 0, sortOverride?: SortState, append = false) => {
      setLoading(true);
      setError(null);

      const currentSort = sortOverride ?? sort;
      try {
        const res = await apiFetch(`/projects/${projectId}/data/query`, {
          method: "POST",
          body: JSON.stringify({
            database,
            sql: `SELECT * FROM "${tableName}"`,
            offset,
            limit: DEFAULT_LIMIT,
            sort_column: currentSort?.column ?? null,
            sort_direction: currentSort?.direction ?? "asc",
          }),
        });
        const data = await res.json();

        if (data.error) {
          setError(data.error);
        }

        if (data.results?.length > 0) {
          const result = data.results[data.results.length - 1];
          setColumns(result.columns);
          setTotalRows(result.total_rows);

          if (append) {
            setRows((prev) => [...prev, ...result.rows]);
          } else {
            setRows(result.rows);
          }
        }
      } catch (e: any) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    },
    [projectId, database, tableName, sort],
  );

  useEffect(() => {
    fetchData();
  }, []);

  const handleSortChange = (newSort: SortState) => {
    setSort(newSort);
    fetchData(0, newSort, false);
  };

  const handleLoadMore = () => {
    if (loading || rows.length >= totalRows) return;
    fetchData(rows.length, sort, true);
  };

  return (
    <div className={styles.container}>
      {error && <div className={styles.error}>{error}</div>}
      {columns.length > 0 ? (
        <DataGrid
          columns={columns}
          rows={rows}
          totalRows={totalRows}
          loading={loading}
          sort={sort}
          onSortChange={handleSortChange}
          onLoadMore={handleLoadMore}
        />
      ) : loading ? (
        <div className={styles.loading}>Loading...</div>
      ) : (
        <div className={styles.empty}>No data</div>
      )}
    </div>
  );
}
