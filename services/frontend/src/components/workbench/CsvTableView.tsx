"use client";

import { useMemo, useRef, useState } from "react";
import Papa from "papaparse";
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  flexRender,
  type ColumnDef,
  type SortingState,
} from "@tanstack/react-table";
import { useVirtualizer } from "@tanstack/react-virtual";
import styles from "./CsvTableView.module.css";

const ROW_HEIGHT = 33;
const OVERSCAN = 20;

interface CsvTableViewProps {
  content: string;
  fileName: string;
}

export function CsvTableView({ content, fileName }: CsvTableViewProps) {
  const { headers, rows, parseError } = useMemo(() => {
    const delimiter = fileName.endsWith(".tsv") ? "\t" : ",";
    const result = Papa.parse<string[]>(content, {
      delimiter,
      skipEmptyLines: true,
      header: false,
    });

    if (result.errors.length > 0 && result.data.length === 0) {
      return { headers: [] as string[], rows: [] as string[][], parseError: result.errors[0].message };
    }

    const [headerRow, ...dataRows] = result.data;
    return { headers: headerRow ?? [], rows: dataRows, parseError: null };
  }, [content, fileName]);

  const columns = useMemo<ColumnDef<string[]>[]>(
    () =>
      headers.map((header, index) => ({
        id: String(index),
        accessorFn: (row: string[]) => row[index] ?? "",
        header: header,
      })),
    [headers],
  );

  const [sorting, setSorting] = useState<SortingState>([]);

  const table = useReactTable({
    data: rows,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  const tableContainerRef = useRef<HTMLDivElement>(null);
  const { rows: tableRows } = table.getRowModel();

  const rowVirtualiser = useVirtualizer({
    count: tableRows.length,
    getScrollElement: () => tableContainerRef.current,
    estimateSize: () => ROW_HEIGHT,
    overscan: OVERSCAN,
  });

  if (parseError) {
    return (
      <div className={styles.container}>
        <div className={styles.error}>
          <div className={styles.errorLabel}>Failed to parse table data</div>
          <div className={styles.errorRaw}>{content.slice(0, 2000)}</div>
        </div>
      </div>
    );
  }

  if (rows.length === 0) {
    return (
      <div className={styles.container}>
        <div className={styles.empty}>No data rows found</div>
      </div>
    );
  }

  const headerGroup = table.getHeaderGroups()[0];

  return (
    <div className={styles.container}>
      <div ref={tableContainerRef} className={styles.tableContainer} role="table">
        <div className={styles.thead} role="row">
          {headerGroup.headers.map((header) => (
            <div
              key={header.id}
              className={styles.th}
              onClick={header.column.getToggleSortingHandler()}
              role="columnheader"
            >
              {flexRender(header.column.columnDef.header, header.getContext())}
              <span className={styles.sortIndicator}>
                {{ asc: " \u25B2", desc: " \u25BC" }[
                  header.column.getIsSorted() as string
                ] ?? ""}
              </span>
            </div>
          ))}
        </div>

        <div
          role="rowgroup"
          style={{ height: `${rowVirtualiser.getTotalSize()}px`, position: "relative" }}
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
    </div>
  );
}
