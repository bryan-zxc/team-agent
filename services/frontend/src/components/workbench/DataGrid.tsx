"use client";

import { useMemo, useRef, useCallback } from "react";
import {
  useReactTable,
  getCoreRowModel,
  flexRender,
  type ColumnDef,
} from "@tanstack/react-table";
import { useVirtualizer } from "@tanstack/react-virtual";
import styles from "./DataGrid.module.css";

const ROW_HEIGHT = 33;
const OVERSCAN = 20;
const SCROLL_THRESHOLD = 200;

type SortState = {
  column: string;
  direction: "asc" | "desc";
} | null;

interface DataGridProps {
  columns: string[];
  rows: any[][];
  totalRows: number;
  loading?: boolean;
  sort: SortState;
  onSortChange: (sort: SortState) => void;
  onLoadMore: () => void;
}

export type { SortState };

export function DataGrid({
  columns,
  rows,
  totalRows,
  loading,
  sort,
  onSortChange,
  onLoadMore,
}: DataGridProps) {
  const columnDefs = useMemo<ColumnDef<any[]>[]>(
    () =>
      columns.map((col, index) => ({
        id: String(index),
        accessorFn: (row: any[]) => row[index] ?? "",
        header: col,
      })),
    [columns],
  );

  const table = useReactTable({
    data: rows,
    columns: columnDefs,
    getCoreRowModel: getCoreRowModel(),
    manualSorting: true,
  });

  const tableContainerRef = useRef<HTMLDivElement>(null);
  const { rows: tableRows } = table.getRowModel();

  const rowVirtualiser = useVirtualizer({
    count: tableRows.length,
    getScrollElement: () => tableContainerRef.current,
    estimateSize: () => ROW_HEIGHT,
    overscan: OVERSCAN,
  });

  const handleScroll = useCallback(() => {
    const el = tableContainerRef.current;
    if (!el || loading) return;
    const { scrollTop, scrollHeight, clientHeight } = el;
    if (scrollHeight - scrollTop - clientHeight < SCROLL_THRESHOLD) {
      if (rows.length < totalRows) {
        onLoadMore();
      }
    }
  }, [loading, rows.length, totalRows, onLoadMore]);

  const handleHeaderClick = (colName: string) => {
    if (sort?.column === colName) {
      if (sort.direction === "asc") {
        onSortChange({ column: colName, direction: "desc" });
      } else {
        onSortChange(null);
      }
    } else {
      onSortChange({ column: colName, direction: "asc" });
    }
  };

  const headerGroup = table.getHeaderGroups()[0];

  return (
    <div className={styles.container}>
      <div
        ref={tableContainerRef}
        className={styles.tableContainer}
        onScroll={handleScroll}
        role="table"
      >
        <div className={styles.thead} role="row">
          {headerGroup.headers.map((header, i) => (
            <div
              key={header.id}
              className={styles.th}
              onClick={() => handleHeaderClick(columns[i])}
              role="columnheader"
            >
              {flexRender(header.column.columnDef.header, header.getContext())}
              <span className={styles.sortIndicator}>
                {sort?.column === columns[i]
                  ? sort.direction === "asc"
                    ? " ▲"
                    : " ▼"
                  : ""}
              </span>
            </div>
          ))}
        </div>

        <div
          role="rowgroup"
          style={{
            height: `${rowVirtualiser.getTotalSize()}px`,
            position: "relative",
          }}
        >
          {rowVirtualiser.getVirtualItems().map((virtualRow) => {
            const row = tableRows[virtualRow.index];
            return (
              <div
                key={row.id}
                className={styles.tr}
                role="row"
                style={{
                  position: "absolute",
                  top: 0,
                  transform: `translateY(${virtualRow.start}px)`,
                  height: `${virtualRow.size}px`,
                }}
              >
                {row.getVisibleCells().map((cell) => (
                  <div key={cell.id} className={styles.td} role="cell">
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </div>
                ))}
              </div>
            );
          })}
        </div>
      </div>

      <div className={styles.statusBar}>
        <span>
          {rows.length} of {totalRows} rows
        </span>
        {loading && <span className={styles.loadingDot}>Loading...</span>}
      </div>
    </div>
  );
}
