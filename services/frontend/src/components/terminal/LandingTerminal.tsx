"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Terminal } from "@xterm/xterm";
import { FitAddon } from "@xterm/addon-fit";
import { WebLinksAddon } from "@xterm/addon-web-links";
import "@xterm/xterm/css/xterm.css";
import { useTerminalWebSocket } from "@/hooks/useTerminalWebSocket";
import { apiFetch } from "@/lib/api";
import { ConfirmCloseDialog } from "./ConfirmCloseDialog";
import styles from "./LandingTerminal.module.css";

type LandingTerminalProps = {
  open: boolean;
  onClose: () => void;
};

function getXtermTheme(): Record<string, string> {
  const isDark = document.documentElement.getAttribute("data-theme") === "dark";
  return {
    background: "#1a1a1a",
    foreground: isDark ? "#e0dcd6" : "#d4d4d4",
    cursor: isDark ? "#e0dcd6" : "#d4d4d4",
    selectionBackground: isDark ? "rgba(143,179,154,0.3)" : "rgba(123,158,135,0.3)",
  };
}

export function LandingTerminal({ open, onClose }: LandingTerminalProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const termRef = useRef<Terminal | null>(null);
  const fitRef = useRef<FitAddon | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [status, setStatus] = useState<"idle" | "loading" | "connected" | "closed">("idle");
  const [showConfirm, setShowConfirm] = useState(false);

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

  // Create session when opened
  useEffect(() => {
    if (!open || sessionId) return;

    let cancelled = false;
    setStatus("loading");

    apiFetch("/terminals", {
      method: "POST",
      body: JSON.stringify({ project_id: null }),
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
  }, [open, sessionId]);

  // Initialise xterm.js when open, connected, and container available
  useEffect(() => {
    if (!open || status !== "connected" || !containerRef.current || termRef.current) return;

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

    // Delay initial fit to allow panel transition to complete
    setTimeout(() => fit.fit(), 300);

    termRef.current = term;
    fitRef.current = fit;

    term.onData((data) => sendInput(data));
    term.onResize(({ cols, rows }) => sendResize(cols, rows));

    return () => {
      term.dispose();
      termRef.current = null;
      fitRef.current = null;
    };
  }, [open, status, sendInput, sendResize]);

  // ResizeObserver
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
  }, [open]);

  // Refit when panel opens
  useEffect(() => {
    if (open && fitRef.current) {
      setTimeout(() => fitRef.current?.fit(), 300);
    }
  }, [open]);

  const handleCloseRequest = useCallback(() => {
    const skip = localStorage.getItem("terminal_close_no_confirm") === "true";
    if (skip) {
      doClose();
    } else {
      setShowConfirm(true);
    }
  }, []);

  const doClose = useCallback(() => {
    setShowConfirm(false);
    if (sessionId) {
      apiFetch(`/terminals/${sessionId}`, { method: "DELETE" }).catch(() => {});
    }
    // Reset state for next open
    termRef.current?.dispose();
    termRef.current = null;
    fitRef.current = null;
    setSessionId(null);
    setStatus("idle");
    onClose();
  }, [sessionId, onClose]);

  return (
    <>
      <div className={`${styles.wrapper} ${open ? styles.wrapperOpen : ""}`}>
        <div className={styles.header}>
          <span className={styles.headerTitle}>Terminal</span>
          <button className={styles.closeBtn} onClick={handleCloseRequest} aria-label="Close terminal">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        <div className={styles.terminalArea}>
          {status === "loading" && (
            <div className={styles.loading}>Starting terminal session...</div>
          )}
          <div ref={containerRef} style={{ width: "100%", height: "100%", display: status === "connected" || status === "closed" ? "block" : "none" }} />
        </div>
      </div>

      {showConfirm && (
        <ConfirmCloseDialog
          onConfirm={doClose}
          onCancel={() => setShowConfirm(false)}
        />
      )}
    </>
  );
}
