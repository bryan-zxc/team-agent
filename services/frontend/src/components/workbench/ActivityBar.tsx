"use client";

import clsx from "clsx";
import { useTheme } from "@/hooks/useTheme";
import styles from "./ActivityBar.module.css";

export type Panel = "chat" | "files" | "data" | "favourites" | "members" | "admin";

type ActivityBarProps = {
  activePanel: Panel;
  onPanelChange: (panel: Panel) => void;
  onOpenTerminal?: () => void;
  coordinatorInitial?: string;
  coordinatorAvatar?: string | null;
  chatBadge?: boolean;
  adminBadge?: boolean;
};

export function ActivityBar({ activePanel, onPanelChange, onOpenTerminal, coordinatorInitial, coordinatorAvatar, chatBadge, adminBadge }: ActivityBarProps) {
  const { theme, toggle } = useTheme();

  return (
    <div className={styles.bar}>
      <div className={styles.topIcons}>
        <button
          className={clsx(styles.icon, activePanel === "chat" && styles.iconActive)}
          onClick={() => onPanelChange("chat")}
          aria-label="Chat"
          title="Chat"
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
          </svg>
          {chatBadge && <span className={styles.badge} />}
        </button>
        <button
          className={clsx(styles.icon, activePanel === "files" && styles.iconActive)}
          onClick={() => onPanelChange("files")}
          aria-label="Files"
          title="Files"
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
            <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
          </svg>
        </button>
        <button
          className={clsx(styles.icon, activePanel === "data" && styles.iconActive)}
          onClick={() => onPanelChange("data")}
          aria-label="Data"
          title="Data"
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
            <ellipse cx="12" cy="5" rx="9" ry="3" />
            <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3" />
            <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5" />
          </svg>
        </button>
        <button
          className={clsx(styles.icon, activePanel === "favourites" && styles.iconActive)}
          onClick={() => onPanelChange("favourites")}
          aria-label="Favourites"
          title="Favourites"
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
            <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
          </svg>
        </button>
        <button
          className={clsx(styles.icon, activePanel === "members" && styles.iconActive)}
          onClick={() => onPanelChange("members")}
          aria-label="Members"
          title="Members"
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
            <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
            <circle cx="12" cy="7" r="4" />
          </svg>
        </button>
        {coordinatorInitial && (
          <button
            className={clsx(styles.icon, activePanel === "admin" && styles.iconActive)}
            onClick={() => onPanelChange("admin")}
            aria-label="Admin"
            title="Admin sessions"
          >
            {coordinatorAvatar ? (
              <img src={coordinatorAvatar} alt="Admin" className={styles.avatarImg} />
            ) : (
              <span className={styles.avatarIcon}>{coordinatorInitial}</span>
            )}
            {adminBadge && <span className={styles.badge} />}
          </button>
        )}
        {onOpenTerminal && (
          <button
            className={styles.icon}
            onClick={onOpenTerminal}
            aria-label="Terminal"
            title="Open terminal"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="4 17 10 11 4 5" />
              <line x1="12" y1="19" x2="20" y2="19" />
            </svg>
          </button>
        )}
      </div>
      <div className={styles.bottomIcons}>
        <button
          className={styles.icon}
          onClick={toggle}
          aria-label="Toggle theme"
          title="Toggle theme"
        >
          {theme === "light" ? (
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
            </svg>
          ) : (
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="5" />
              <line x1="12" y1="1" x2="12" y2="3" />
              <line x1="12" y1="21" x2="12" y2="23" />
              <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" />
              <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
              <line x1="1" y1="12" x2="3" y2="12" />
              <line x1="21" y1="12" x2="23" y2="12" />
              <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" />
              <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
            </svg>
          )}
        </button>
      </div>
    </div>
  );
}
