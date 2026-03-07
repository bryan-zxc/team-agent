"use client";

import clsx from "clsx";
import { useCallback, useEffect, useRef, useState } from "react";
import Editor, { type Monaco } from "@monaco-editor/react";
import { useTheme } from "@/hooks/useTheme";
import { apiFetch } from "@/lib/api";
import { DataGrid, type SortState } from "./DataGrid";
import { SaveQueryDialog } from "./SaveQueryDialog";
import type { IDockviewPanelProps } from "dockview";
import styles from "./SqlTab.module.css";

const DEFAULT_LIMIT = 100;

type ResultTab = {
  columns: string[];
  rows: any[][];
  totalRows: number;
  statementIndex: number;
  sql: string;
};

type SqlTabParams = {
  filePath?: string;
  projectId: string;
  database?: string;
  prefillSql?: string;
  onSavedOverwrite?: (filePath: string, keepPanelId: string) => void;
};

function defineThemes(monaco: Monaco) {
  monaco.editor.defineTheme("team-agent-light", {
    base: "vs",
    inherit: true,
    rules: [],
    colors: {
      "editor.background": "#FAF8F5",
      "editor.foreground": "#2C2A27",
      "editorLineNumber.foreground": "#B0AAA0",
      "editorLineNumber.activeForeground": "#7A756D",
      "editor.selectionBackground": "#E4EDE7",
      "editor.lineHighlightBackground": "#F0EDE8",
      "editorCursor.foreground": "#7B9E87",
      "editorIndentGuide.background": "#E4E0D8",
    },
  });

  monaco.editor.defineTheme("team-agent-dark", {
    base: "vs-dark",
    inherit: true,
    rules: [],
    colors: {
      "editor.background": "#1C1B19",
      "editor.foreground": "#E0DCD6",
      "editorLineNumber.foreground": "#555250",
      "editorLineNumber.activeForeground": "#8E8983",
      "editor.selectionBackground": "rgba(143, 179, 154, 0.25)",
      "editor.lineHighlightBackground": "#222120",
      "editorCursor.foreground": "#8FB39A",
      "editorIndentGuide.background": "#2E2D2B",
    },
  });
}

export function SqlTab({ params, api: panelApi }: IDockviewPanelProps<SqlTabParams>) {
  const { filePath, projectId, database = "data", prefillSql, onSavedOverwrite } = params;
  const { theme } = useTheme();
  const monacoTheme =
    theme === "dark" ? "team-agent-dark" : "team-agent-light";
  const monacoRef = useRef<Monaco | null>(null);

  const [sql, setSql] = useState(prefillSql ?? "");
  const [savePath, setSavePath] = useState<string | null>(filePath ?? null);
  const [saving, setSaving] = useState(false);
  const [resultTabs, setResultTabs] = useState<ResultTab[]>([]);
  const [activeResultIdx, setActiveResultIdx] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sort, setSort] = useState<SortState>(null);
  const [dividerY, setDividerY] = useState(300);
  const [showSaveDialog, setShowSaveDialog] = useState(false);
  const runRef = useRef<() => void>(undefined);
  const saveRef = useRef<() => void>(undefined);

  // Load .sql file content if opened from a file
  useEffect(() => {
    if (!filePath) return;
    apiFetch(
      `/projects/${projectId}/files/content?path=${encodeURIComponent(filePath)}`,
    )
      .then((r) => r.json())
      .then((data) => setSql(data.content))
      .catch(() => {});
  }, [filePath, projectId]);

  useEffect(() => {
    if (monacoRef.current) {
      monacoRef.current.editor.setTheme(monacoTheme);
    }
  }, [monacoTheme]);

  const executeQuery = useCallback(
    async (
      overrideSql?: string,
      offset = 0,
      sortOverride?: SortState,
      append = false,
    ) => {
      const queryStr = overrideSql ?? sql;
      if (!queryStr.trim()) return;
      setLoading(true);
      setError(null);

      const currentSort = sortOverride ?? sort;
      try {
        const res = await apiFetch(`/projects/${projectId}/data/query`, {
          method: "POST",
          body: JSON.stringify({
            database,
            sql: queryStr,
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

        if (append && data.results?.length > 0) {
          setResultTabs((prev) => {
            const updated = [...prev];
            const last = data.results[data.results.length - 1];
            const target = updated[updated.length - 1];
            if (target) {
              target.rows = [...target.rows, ...last.rows];
              target.totalRows = last.total_rows;
            }
            return updated;
          });
        } else if (data.results) {
          const tabs: ResultTab[] = data.results
            .filter((r: any) => r.columns.length > 0)
            .map((r: any) => ({
              columns: r.columns,
              rows: r.rows,
              totalRows: r.total_rows,
              statementIndex: r.statement_index,
              sql: queryStr,
            }));
          setResultTabs(tabs);
          setActiveResultIdx(0);
        }
      } catch (e: any) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    },
    [sql, sort, projectId, database],
  );

  const handleRun = useCallback(() => {
    setSort(null);
    executeQuery(undefined, 0, null, false);
  }, [executeQuery]);

  const handleSave = useCallback(() => {
    if (savePath) {
      saveToPath(savePath);
    } else {
      setShowSaveDialog(true);
    }
  }, [savePath]);

  const saveToPath = useCallback(
    async (targetPath: string) => {
      setSaving(true);
      setError(null);
      setShowSaveDialog(false);
      try {
        const res = await apiFetch(
          `/projects/${projectId}/files/content?path=${encodeURIComponent(targetPath)}`,
          { method: "PUT", body: JSON.stringify({ content: sql }) },
        );
        if (!res.ok) throw new Error("Failed to save");
        setSavePath(targetPath);
        const fileName = targetPath.split("/").pop() ?? targetPath;
        panelApi.setTitle(fileName);
        panelApi.updateParameters({ filePath: targetPath });
        onSavedOverwrite?.(targetPath, panelApi.id);
      } catch (e: any) {
        setError(e.message ?? "Save failed");
      } finally {
        setSaving(false);
      }
    },
    [sql, projectId, panelApi],
  );

  // Keep refs in sync for Monaco actions
  runRef.current = handleRun;
  saveRef.current = handleSave;

  const handleSortChange = (newSort: SortState) => {
    setSort(newSort);
    const active = resultTabs[activeResultIdx];
    if (active) {
      executeQuery(active.sql, 0, newSort, false);
    }
  };

  const handleLoadMore = () => {
    const active = resultTabs[activeResultIdx];
    if (!active || loading) return;
    executeQuery(active.sql, active.rows.length, sort, true);
  };

  const handleDividerMouseDown = (e: React.MouseEvent) => {
    e.preventDefault();
    const startY = e.clientY;
    const startDivider = dividerY;
    const onMouseMove = (ev: MouseEvent) => {
      setDividerY(Math.max(100, startDivider + ev.clientY - startY));
    };
    const onMouseUp = () => {
      document.removeEventListener("mousemove", onMouseMove);
      document.removeEventListener("mouseup", onMouseUp);
    };
    document.addEventListener("mousemove", onMouseMove);
    document.addEventListener("mouseup", onMouseUp);
  };

  const handleBeforeMount = useCallback((monaco: Monaco) => {
    monacoRef.current = monaco;
    defineThemes(monaco);
  }, []);

  const activeResult = resultTabs[activeResultIdx];

  return (
    <div className={styles.container}>
      <div className={styles.editorPane} style={{ height: dividerY }}>
        <div className={styles.toolbar}>
          <button
            className={styles.runBtn}
            onClick={handleRun}
            disabled={loading}
          >
            {loading ? "Running..." : "Run"}
          </button>
          <button
            className={styles.saveBtn}
            onClick={handleSave}
            disabled={saving}
          >
            {saving ? "Saving..." : "Save"}
          </button>
        </div>
        <Editor
          language="sql"
          theme={monacoTheme}
          value={sql}
          onChange={(v) => setSql(v ?? "")}
          beforeMount={handleBeforeMount}
          onMount={(editor) => {
            editor.addAction({
              id: "run-query",
              label: "Run Query",
              keybindings: [2048 | 3],
              run: () => runRef.current?.(),
            });
            editor.addAction({
              id: "save-query",
              label: "Save Query",
              keybindings: [2048 | 49],
              run: () => saveRef.current?.(),
            });
          }}
          options={{
            minimap: { enabled: false },
            fontSize: 13,
            fontFamily: "var(--font-mono)",
            lineNumbers: "on",
            scrollBeyondLastLine: false,
            renderLineHighlight: "line",
            padding: { top: 12 },
            scrollbar: {
              verticalScrollbarSize: 6,
              horizontalScrollbarSize: 6,
            },
          }}
        />
      </div>

      <div className={styles.divider} onMouseDown={handleDividerMouseDown} />

      <div className={styles.resultsPane}>
        {error && <div className={styles.error}>{error}</div>}

        {resultTabs.length > 1 && (
          <div className={styles.resultTabs}>
            {resultTabs.map((rt, i) => (
              <button
                key={i}
                className={clsx(
                  styles.resultTab,
                  i === activeResultIdx && styles.resultTabActive,
                )}
                onClick={() => setActiveResultIdx(i)}
              >
                Result {rt.statementIndex + 1}
              </button>
            ))}
          </div>
        )}

        {activeResult ? (
          <DataGrid
            columns={activeResult.columns}
            rows={activeResult.rows}
            totalRows={activeResult.totalRows}
            loading={loading}
            sort={sort}
            onSortChange={handleSortChange}
            onLoadMore={handleLoadMore}
          />
        ) : (
          <div className={styles.emptyResults}>
            Run a query to see results
          </div>
        )}
      </div>

      <SaveQueryDialog
        open={showSaveDialog}
        projectId={projectId}
        onClose={() => setShowSaveDialog(false)}
        onSave={saveToPath}
      />
    </div>
  );
}
