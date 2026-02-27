"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Editor, { type Monaco } from "@monaco-editor/react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useTheme } from "@/hooks/useTheme";
import { getLanguage } from "@/lib/fileIcons";
import { apiFetch } from "@/lib/api";
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
  const monacoTheme = theme === "dark" ? "team-agent-dark" : "team-agent-light";
  const [previewMode, setPreviewMode] = useState(isMarkdown);
  const [wordWrap, setWordWrap] = useState<"on" | "off">(
    isMarkdown ? "on" : "off",
  );

  useEffect(() => {
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
  }, [filePath, projectId]);

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
      if (isMarkdown) setPreviewMode(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }, [editContent, filePath, projectId]);

  const handleBeforeMount = useCallback((monaco: Monaco) => {
    monacoRef.current = monaco;
    defineThemes(monaco);
  }, []);

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
          {isMarkdown ? (
            <>
              <div className={styles.toggleGroup}>
                <button
                  className={`${styles.toggleBtn} ${previewMode ? styles.toggleBtnActive : ""}`}
                  onClick={() => { setEditing(false); setPreviewMode(true); }}
                >
                  Preview
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
      {isMarkdown && previewMode ? (
        <div className={styles.markdownPreview}>
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
        </div>
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
