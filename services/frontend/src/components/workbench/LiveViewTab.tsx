"use client";

import { useCallback, useRef, useState } from "react";
import type { IDockviewPanelProps } from "dockview";
import { useScreencastWebSocket } from "@/hooks/useScreencastWebSocket";
import styles from "./LiveViewTab.module.css";

type LiveViewTabParams = {
  workloadId: string;
  onClose?: () => void;
};

export function LiveViewTab({ params }: IDockviewPanelProps<LiveViewTabParams>) {
  const { workloadId, onClose } = params;
  const imgRef = useRef<HTMLImageElement>(null);
  const [status, setStatus] = useState<"connecting" | "streaming" | "stopped">("connecting");

  const onFrame = useCallback((data: string) => {
    if (imgRef.current) {
      imgRef.current.src = `data:image/jpeg;base64,${data}`;
    }
    setStatus((prev) => (prev === "streaming" ? prev : "streaming"));
  }, []);

  const onStopped = useCallback(() => {
    setStatus("stopped");
    if (onClose) {
      setTimeout(onClose, 1500);
    }
  }, [onClose]);

  useScreencastWebSocket({ workloadId, onFrame, onStopped });

  return (
    <div className={styles.container}>
      <div className={styles.toolbar}>
        <span className={styles.statusDot} data-status={status} />
        <span className={styles.title}>Live View</span>
      </div>
      <div className={styles.viewport}>
        {status === "connecting" && (
          <div className={styles.loading}>Connecting to browser...</div>
        )}
        <img ref={imgRef} className={styles.frame} alt="Browser live view" />
        {status === "stopped" && (
          <div className={styles.overlay}>Browser session ended</div>
        )}
      </div>
    </div>
  );
}
