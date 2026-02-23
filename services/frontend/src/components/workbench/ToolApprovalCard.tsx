"use client";

import { useCallback, useRef, useState } from "react";
import { DiffEditor, type Monaco } from "@monaco-editor/react";
import { useTheme } from "@/hooks/useTheme";
import { getLanguage } from "@/lib/fileIcons";
import type { ToolApprovalBlock } from "@/types";
import styles from "./ToolApprovalCard.module.css";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type Decision = "approve" | "approve_session" | "approve_project" | "deny";

type Props = {
  block: ToolApprovalBlock;
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
      "diffEditor.insertedTextBackground": "rgba(123,158,135,0.15)",
      "diffEditor.removedTextBackground": "rgba(204,68,68,0.12)",
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
      "diffEditor.insertedTextBackground": "rgba(143,179,154,0.18)",
      "diffEditor.removedTextBackground": "rgba(214,102,102,0.15)",
    },
  });
}

function getFilePath(toolInput: Record<string, unknown>): string | null {
  if (typeof toolInput.file_path === "string") return toolInput.file_path;
  return null;
}

function computeModified(block: ToolApprovalBlock): string {
  const { tool_name, tool_input, original_content } = block;

  if (tool_name === "Write" && typeof tool_input.content === "string") {
    return tool_input.content;
  }

  if (tool_name === "Edit" && original_content != null) {
    const oldStr = typeof tool_input.old_string === "string" ? tool_input.old_string : "";
    const newStr = typeof tool_input.new_string === "string" ? tool_input.new_string : "";
    if (oldStr && original_content.includes(oldStr)) {
      return original_content.replace(oldStr, newStr);
    }
    return original_content;
  }

  return original_content ?? "";
}

function isWriteOrEdit(toolName: string): boolean {
  return toolName === "Write" || toolName === "Edit" || toolName === "MultiEdit";
}

function toolVerb(toolName: string): string {
  switch (toolName) {
    case "Bash": return "wants to run";
    case "Write": return "wants to write";
    case "Edit": return "wants to edit";
    case "MultiEdit": return "wants to edit";
    case "Read": return "wants to read";
    default: return "wants to use";
  }
}

export function ToolApprovalCard({ block }: Props) {
  const { theme } = useTheme();
  const monacoRef = useRef<Monaco | null>(null);
  const [status, setStatus] = useState<"pending" | "deny_input" | Decision>("pending");
  const [denyReason, setDenyReason] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const monacoTheme = theme === "dark" ? "team-agent-dark" : "team-agent-light";
  const filePath = getFilePath(block.tool_input);
  const fileName = filePath?.split("/").pop() ?? "";
  const language = fileName ? getLanguage(fileName) : "plaintext";
  const showDiff = isWriteOrEdit(block.tool_name) && block.original_content != null;

  const handleBeforeMount = useCallback((monaco: Monaco) => {
    monacoRef.current = monaco;
    defineThemes(monaco);
  }, []);

  const submitDecision = useCallback(
    async (decision: Decision, reason?: string) => {
      setSubmitting(true);
      try {
        await fetch(
          `${API_URL}/workloads/${block.workload_id}/tool-approval`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              approval_request_id: block.approval_request_id,
              decision,
              tool_name: block.tool_name,
              reason: reason || null,
            }),
          },
        );
        setStatus(decision);
      } catch {
        setSubmitting(false);
      }
    },
    [block],
  );

  const handleDenySubmit = useCallback(() => {
    if (!denyReason.trim()) return;
    submitDecision("deny", denyReason.trim());
  }, [denyReason, submitDecision]);

  // Resolved state — compact one-liner
  if (status === "approve" || status === "approve_session" || status === "approve_project" || status === "deny") {
    const approved = status !== "deny";
    const tierLabel =
      status === "approve_session" ? " for session" :
      status === "approve_project" ? " for project" : "";
    return (
      <div className={styles.card}>
        <div className={styles.resolvedRow}>
          <span className={styles.toolBadge}>{block.tool_name}</span>
          <span className={styles.resolvedSummary}>{block.input_summary}</span>
          <span className={approved ? styles.resolvedApproved : styles.resolvedDenied}>
            {approved ? `Approved${tierLabel}` : "Denied"}
          </span>
        </div>
      </div>
    );
  }

  // Deny input state
  if (status === "deny_input") {
    return (
      <div className={styles.card}>
        <div className={styles.header}>
          <span className={styles.toolBadge}>{block.tool_name}</span>
          <span className={styles.headerLabel}>
            {toolVerb(block.tool_name)}{" "}
            <span className={styles.headerSummary}>{block.input_summary}</span>
          </span>
        </div>
        <div className={styles.denySection}>
          <textarea
            className={styles.denyTextarea}
            placeholder="Explain why this tool call should be denied..."
            value={denyReason}
            onChange={(e) => setDenyReason(e.target.value)}
            autoFocus
          />
          <div className={styles.denyActions}>
            <button
              className={styles.btnCancel}
              onClick={() => setStatus("pending")}
              disabled={submitting}
            >
              Cancel
            </button>
            <button
              className={styles.btnDeny}
              onClick={handleDenySubmit}
              disabled={submitting || !denyReason.trim()}
            >
              Deny with Reason
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Pending state — full approval card
  return (
    <div className={styles.card}>
      <div className={styles.header}>
        <span className={styles.toolBadge}>{block.tool_name}</span>
        <span className={styles.headerLabel}>
          {toolVerb(block.tool_name)}{" "}
          <span className={styles.headerSummary}>{block.input_summary}</span>
        </span>
      </div>

      {block.tool_name === "Bash" && typeof block.tool_input.command === "string" && (
        <div className={styles.commandBox}>
          <code>{block.tool_input.command}</code>
        </div>
      )}

      {showDiff && (
        <div className={styles.diffContainer}>
          {filePath && <div className={styles.diffFilePath}>{filePath}</div>}
          <div className={styles.diffEditor}>
            <DiffEditor
              original={block.original_content ?? ""}
              modified={computeModified(block)}
              language={language}
              theme={monacoTheme}
              beforeMount={handleBeforeMount}
              options={{
                readOnly: true,
                minimap: { enabled: false },
                fontSize: 12,
                fontFamily: "var(--font-mono)",
                lineNumbers: "on",
                scrollBeyondLastLine: false,
                renderSideBySide: true,
                scrollbar: {
                  verticalScrollbarSize: 6,
                  horizontalScrollbarSize: 6,
                },
                padding: { top: 8 },
              }}
            />
          </div>
        </div>
      )}

      <div className={styles.actions}>
        <button
          className={styles.btnApprove}
          onClick={() => submitDecision("approve")}
          disabled={submitting}
        >
          Approve
        </button>
        <button
          className={styles.btnSession}
          onClick={() => submitDecision("approve_session")}
          disabled={submitting}
        >
          For Session
        </button>
        <button
          className={styles.btnProject}
          onClick={() => submitDecision("approve_project")}
          disabled={submitting}
        >
          For Project
        </button>
        <button
          className={styles.btnDenyOutline}
          onClick={() => setStatus("deny_input")}
          disabled={submitting}
        >
          Deny
        </button>
      </div>
    </div>
  );
}
