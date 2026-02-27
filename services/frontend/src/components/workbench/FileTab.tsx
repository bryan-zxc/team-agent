"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Editor, { type Monaco } from "@monaco-editor/react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useTheme } from "@/hooks/useTheme";
import { getLanguage } from "@/lib/fileIcons";
import { API_URL, apiFetch } from "@/lib/api";
import { JsonTreeView } from "./JsonTreeView";
import { CsvTableView } from "./CsvTableView";
import type { IDockviewPanelProps } from "dockview";
import styles from "./FileTab.module.css";

type FileTabParams = {
  filePath: string;
  projectId: string;
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

export function FileTab({ params }: IDockviewPanelProps<FileTabParams>) {
  const { filePath, projectId } = params;
  const { theme } = useTheme();
  const [content, setContent] = useState<string | null>(null);
  const [editContent, setEditContent] = useState<string>("");
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const monacoRef = useRef<Monaco | null>(null);

  const fileName = filePath.split("/").pop() ?? "";
  const language = getLanguage(fileName);
  const isMarkdown = language === "markdown";
  const isHtml = language === "html";
  const isJson = language === "json";
  const isSvg = fileName.endsWith(".svg");
  const isCsv = fileName.endsWith(".csv") || fileName.endsWith(".tsv");
  const isImage = /\.(png|jpg|jpeg|gif|webp)$/i.test(fileName);
  const hasPreview = isMarkdown || isHtml || isJson || isSvg || isCsv;
  const previewLabel = isJson ? "Tree" : isCsv ? "Table" : "Preview";
  const monacoTheme = theme === "dark" ? "team-agent-dark" : "team-agent-light";
  const [previewMode, setPreviewMode] = useState(hasPreview);
  const [wordWrap, setWordWrap] = useState<"on" | "off">(
    isMarkdown ? "on" : "off",
  );

  useEffect(() => {
    if (isImage) return;
    apiFetch(`/projects/${projectId}/files/content?path=${encodeURIComponent(filePath)}`)
      .then((r) => {
        if (!r.ok) throw new Error("Failed to load file");
        return r.json();
      })
      .then((data) => {
        setContent(data.content);
        setEditContent(data.content);
      })
      .catch((err) => setError(err.message));
  }, [filePath, projectId, isImage]);

  useEffect(() => {
    if (monacoRef.current) {
      monacoRef.current.editor.setTheme(monacoTheme);
    }
  }, [monacoTheme]);

  const handleSave = useCallback(async () => {
    setSaving(true);
    try {
      const res = await apiFetch(
        `/projects/${projectId}/files/content?path=${encodeURIComponent(filePath)}`,
        {
          method: "PUT",
          body: JSON.stringify({ content: editContent }),
        },
      );
      if (!res.ok) throw new Error("Failed to save");
      setContent(editContent);
      setEditing(false);
      if (hasPreview) setPreviewMode(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }, [editContent, filePath, projectId]);

  useEffect(() => {
    if (!editing) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "s") {
        e.preventDefault();
        handleSave();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [editing, handleSave]);

  const handleBeforeMount = useCallback((monaco: Monaco) => {
    monacoRef.current = monaco;
    defineThemes(monaco);
  }, []);

  if (isImage) {
    return (
      <div className={styles.container}>
        <div className={styles.toolbar}>
          <span className={styles.filePath}>{filePath}</span>
        </div>
        <div className={styles.imagePreview}>
          <img
            src={`${API_URL}/projects/${projectId}/raw/${filePath}`}
            alt={fileName}
          />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={styles.container}>
        <div className={styles.errorState}>
          <p className={styles.errorText}>{error}</p>
        </div>
      </div>
    );
  }

  if (content === null) {
    return (
      <div className={styles.container}>
        <div className={styles.loadingState}>
          <p className={styles.loadingText}>Loading...</p>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.container}>
      <div className={styles.toolbar}>
        <span className={styles.filePath}>{filePath}</span>
        <div className={styles.toolbarActions}>
          {hasPreview ? (
            <>
              <div className={styles.toggleGroup}>
                <button
                  className={`${styles.toggleBtn} ${previewMode ? styles.toggleBtnActive : ""}`}
                  onClick={() => { setEditing(false); setPreviewMode(true); }}
                >
                  {previewLabel}
                </button>
                <button
                  className={`${styles.toggleBtn} ${!previewMode ? styles.toggleBtnActive : ""}`}
                  onClick={() => { setPreviewMode(false); setEditing(true); }}
                >
                  Edit
                </button>
              </div>
              {editing && (
                <>
                  <button
                    className={`${styles.toolbarBtn} ${wordWrap === "on" ? styles.toolbarBtnActive : ""}`}
                    onClick={() => setWordWrap((w) => (w === "on" ? "off" : "on"))}
                    title={wordWrap === "on" ? "Disable word wrap" : "Enable word wrap"}
                  >
                    Wrap
                  </button>
                  <button
                    className={styles.toolbarBtn}
                    onClick={() => {
                      setEditContent(content);
                      setEditing(false);
                      setPreviewMode(true);
                    }}
                  >
                    Cancel
                  </button>
                  <button
                    className={styles.toolbarBtnPrimary}
                    onClick={handleSave}
                    disabled={saving}
                  >
                    {saving ? "Saving..." : "Save"}
                  </button>
                </>
              )}
            </>
          ) : (
            <>
              <button
                className={`${styles.toolbarBtn} ${wordWrap === "on" ? styles.toolbarBtnActive : ""}`}
                onClick={() => setWordWrap((w) => (w === "on" ? "off" : "on"))}
                title={wordWrap === "on" ? "Disable word wrap" : "Enable word wrap"}
              >
                Wrap
              </button>
              {editing ? (
                <>
                  <button
                    className={styles.toolbarBtn}
                    onClick={() => {
                      setEditContent(content);
                      setEditing(false);
                    }}
                  >
                    Cancel
                  </button>
                  <button
                    className={styles.toolbarBtnPrimary}
                    onClick={handleSave}
                    disabled={saving}
                  >
                    {saving ? "Saving..." : "Save"}
                  </button>
                </>
              ) : (
                <button className={styles.toolbarBtn} onClick={() => setEditing(true)}>
                  Edit
                </button>
              )}
            </>
          )}
        </div>
      </div>
      {hasPreview && previewMode ? (
        isMarkdown ? (
          <div className={styles.markdownPreview}>
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
          </div>
        ) : isJson ? (
          <JsonTreeView data={content} />
        ) : isCsv ? (
          <CsvTableView content={content} fileName={fileName} />
        ) : isSvg ? (
          <div className={styles.svgPreview}>
            <img
              src={`${API_URL}/projects/${projectId}/raw/${filePath}`}
              alt={fileName}
            />
          </div>
        ) : (
          <div className={styles.htmlPreview}>
            <iframe
              src={`${API_URL}/projects/${projectId}/raw/${filePath}`}
              sandbox="allow-scripts allow-same-origin"
              title={fileName}
            />
          </div>
        )
      ) : (
        <div className={styles.editorWrapper}>
          <Editor
            language={language}
            value={editing ? editContent : content}
            theme={monacoTheme}
            onChange={(value) => setEditContent(value ?? "")}
            beforeMount={handleBeforeMount}
            options={{
              readOnly: !editing,
              minimap: { enabled: false },
              fontSize: 13,
              fontFamily: "var(--font-mono)",
              lineNumbers: "on",
              scrollBeyondLastLine: false,
              renderLineHighlight: "line",
              wordWrap,
              padding: { top: 12 },
              scrollbar: {
                verticalScrollbarSize: 6,
                horizontalScrollbarSize: 6,
              },
            }}
          />
        </div>
      )}
    </div>
  );
}
