"use client";

import React, { useCallback, useRef } from "react";
import type { IDockviewPanelHeaderProps } from "dockview-core";
import { getFileIcon } from "@/lib/fileIcons";
import { SetiIcon } from "./SetiIcon";

function useTitle(api: IDockviewPanelHeaderProps["api"]) {
  const [title, setTitle] = React.useState(api.title);
  React.useEffect(() => {
    const disposable = api.onDidTitleChange((event: { title: string }) => {
      setTitle(event.title);
    });
    if (title !== api.title) {
      setTitle(api.title);
    }
    return () => disposable.dispose();
  }, [api]);
  return title;
}

const ChatIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
  </svg>
);

const CloseIcon = () => (
  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="18" y1="6" x2="6" y2="18" />
    <line x1="6" y1="6" x2="18" y2="18" />
  </svg>
);

export const TabIcon: React.FunctionComponent<IDockviewPanelHeaderProps> = ({ api, containerApi: _containerApi, params: _params }) => {
  const title = useTitle(api);
  const isMiddleMouseButton = useRef(false);

  const isRoom = api.id.startsWith("room-");

  const onClose = useCallback((event: React.MouseEvent) => {
    event.preventDefault();
    api.close();
  }, [api]);

  const onBtnPointerDown = useCallback((event: React.PointerEvent) => {
    event.preventDefault();
  }, []);

  const onPointerDown = useCallback((event: React.PointerEvent) => {
    isMiddleMouseButton.current = event.button === 1;
  }, []);

  const onPointerUp = useCallback((event: React.PointerEvent) => {
    if (isMiddleMouseButton.current && event.button === 1) {
      isMiddleMouseButton.current = false;
      onClose(event);
    }
  }, [onClose]);

  const onPointerLeave = useCallback(() => {
    isMiddleMouseButton.current = false;
  }, []);

  return (
    <div
      className="dv-default-tab"
      onPointerDown={onPointerDown}
      onPointerUp={onPointerUp}
      onPointerLeave={onPointerLeave}
    >
      <span className="dv-default-tab-content" style={{ display: "flex", alignItems: "center", gap: "6px" }}>
        {isRoom ? <ChatIcon /> : <SetiIcon svg={getFileIcon(title ?? "")} size={14} />}
        {title}
      </span>
      <div className="dv-default-tab-action" onPointerDown={onBtnPointerDown} onClick={onClose}>
        <CloseIcon />
      </div>
    </div>
  );
};
