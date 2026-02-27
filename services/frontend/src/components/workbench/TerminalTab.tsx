"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { IDockviewPanelProps } from "dockview";
import { Terminal } from "@xterm/xterm";
import { FitAddon } from "@xterm/addon-fit";
import { WebLinksAddon } from "@xterm/addon-web-links";
import "@xterm/xterm/css/xterm.css";
import { useTerminalWebSocket } from "@/hooks/useTerminalWebSocket";
import { apiFetch } from "@/lib/api";
import styles from "./TerminalTab.module.css";

type TerminalTabParams = {
  projectId: string;
};

function getXtermTheme(): Record<string, string> {
  const isDark = document.documentElement.getAttribute("data-theme") === "dark";
  return {
    background: isDark ? "#1a1a1a" : "#1a1a1a",
    foreground: isDark ? "#e0dcd6" : "#d4d4d4",
    cursor: isDark ? "#e0dcd6" : "#d4d4d4",
    selectionBackground: isDark ? "rgba(143,179,154,0.3)" : "rgba(123,158,135,0.3)",
  };
}

export function TerminalTab({ api, params }: IDockviewPanelProps<TerminalTabParams>) {
  const { projectId } = params;
  const containerRef = useRef<HTMLDivElement>(null);
  const termRef = useRef<Terminal | null>(null);
  const fitRef = useRef<FitAddon | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [status, setStatus] = useState<"loading" | "connected" | "closed">("loading");

  const onData = useCallback((data: Uint8Array) => {
    termRef.current?.write(data);
  }, []);

  const onClosed = useCallback(() => {
    setStatus("closed");
    termRef.current?.write("\r\n\x1b[90m[Session ended]\x1b[0m\r\n");
  }, []);

  const { sendInput, sendResize } = useTerminalWebSocket({
    sessionId,
    onData,
    onClosed,
  });

  // Create terminal session
  useEffect(() => {
    let cancelled = false;

    apiFetch("/terminals", {
      method: "POST",
      body: JSON.stringify({ project_id: projectId }),
    })
      .then((r) => r.json())
      .then((data) => {
        if (!cancelled) {
          setSessionId(data.session_id);
          setStatus("connected");
        }
      })
      .catch(() => {
        if (!cancelled) setStatus("closed");
      });

    return () => {
      cancelled = true;
    };
  }, [projectId]);

  // Initialise xterm.js
  useEffect(() => {
    if (status !== "connected" || !containerRef.current || termRef.current) return;

    const term = new Terminal({
      cursorBlink: true,
      fontSize: 13,
      fontFamily: "'SF Mono', 'Fira Code', 'Cascadia Code', monospace",
      theme: getXtermTheme(),
      allowProposedApi: true,
    });

    const fit = new FitAddon();
    term.loadAddon(fit);
    term.loadAddon(new WebLinksAddon());
    term.open(containerRef.current);
    fit.fit();

    termRef.current = term;
    fitRef.current = fit;

    term.onData((data) => sendInput(data));
    term.onResize(({ cols, rows }) => sendResize(cols, rows));

    return () => {
      term.dispose();
      termRef.current = null;
      fitRef.current = null;
    };
  }, [status, sendInput, sendResize]);

  // ResizeObserver for container
  useEffect(() => {
    const el = containerRef.current;
    if (!el || !fitRef.current) return;

    const ro = new ResizeObserver(() => {
      try {
        fitRef.current?.fit();
      } catch {
        // Ignore fit errors during teardown
      }
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // Refit when panel becomes visible
  useEffect(() => {
    const disposable = api.onDidVisibilityChange((event) => {
      if (event.isVisible) {
        setTimeout(() => fitRef.current?.fit(), 50);
      }
    });
    return () => disposable.dispose();
  }, [api]);

  // Cleanup session on unmount
  useEffect(() => {
    return () => {
      if (sessionId) {
        apiFetch(`/terminals/${sessionId}`, { method: "DELETE" }).catch(() => {});
      }
    };
  }, [sessionId]);

  return (
    <div className={styles.container}>
      {status === "loading" && (
        <div className={styles.loading}>Starting terminal session...</div>
      )}
      <div ref={containerRef} style={{ width: "100%", height: "100%", display: status === "loading" ? "none" : "block" }} />
    </div>
  );
}
