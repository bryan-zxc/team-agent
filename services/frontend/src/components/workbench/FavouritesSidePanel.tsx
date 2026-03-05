"use client";

import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import styles from "./FavouritesSidePanel.module.css";

type Favourite = {
  path: string;
  label: string;
};

const DEFAULT_FAVOURITES: Favourite[] = [
  { path: "docs/governance/board.html", label: "Board" },
  { path: "docs/governance/timeline.html", label: "Timeline" },
];

function storageKey(projectId: string) {
  return `favourites:${projectId}`;
}

function loadFavourites(projectId: string): Favourite[] | null {
  try {
    const raw = localStorage.getItem(storageKey(projectId));
    if (raw) return JSON.parse(raw);
  } catch {}
  return null;
}

function saveFavourites(projectId: string, favs: Favourite[]) {
  try {
    localStorage.setItem(storageKey(projectId), JSON.stringify(favs));
  } catch {}
}

async function resolveDefaults(projectId: string): Promise<Favourite[]> {
  const results = await Promise.all(
    DEFAULT_FAVOURITES.map(async (fav) => {
      try {
        const resp = await apiFetch(
          `/projects/${projectId}/files/content?path=${encodeURIComponent(fav.path)}`,
        );
        return resp.ok ? fav : null;
      } catch {
        return null;
      }
    }),
  );
  return results.filter((f): f is Favourite => f !== null);
}

type FavouritesSidePanelProps = {
  projectId: string;
  onFileClick: (filePath: string) => void;
};

export function FavouritesSidePanel({ projectId, onFileClick }: FavouritesSidePanelProps) {
  const [favourites, setFavourites] = useState<Favourite[]>(() => loadFavourites(projectId) ?? []);

  useEffect(() => {
    const saved = loadFavourites(projectId);
    if (saved) {
      setFavourites(saved);
      return;
    }
    let cancelled = false;
    resolveDefaults(projectId).then((defaults) => {
      if (cancelled) return;
      saveFavourites(projectId, defaults);
      setFavourites(defaults);
    });
    return () => { cancelled = true; };
  }, [projectId]);

  const handleUnpin = useCallback((path: string) => {
    setFavourites((prev) => {
      const next = prev.filter((f) => f.path !== path);
      saveFavourites(projectId, next);
      return next;
    });
  }, [projectId]);

  return (
    <div className={styles.panel}>
      <div className={styles.header}>
        <div className={styles.logo}>
          <div className={styles.logoMark}>ta</div>
          <span className={styles.logoText}>Team Agent</span>
        </div>
      </div>

      <div className={styles.sectionHeader}>
        <span className={styles.sectionLabel}>Favourites</span>
      </div>

      <div className={styles.list}>
        {favourites.length === 0 && (
          <div className={styles.emptyState}>No pinned files</div>
        )}
        {favourites.map((fav) => (
          <div
            key={fav.path}
            className={styles.item}
            role="button"
            tabIndex={0}
            onClick={() => onFileClick(fav.path)}
            onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") onFileClick(fav.path); }}
            title={fav.path}
          >
            <svg className={styles.itemIcon} width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
              <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
            </svg>
            <span className={styles.itemLabel}>{fav.label}</span>
            <span className={styles.itemPath}>{fav.path.split("/").pop()}</span>
            <button
              className={styles.unpinBtn}
              onClick={(e) => { e.stopPropagation(); handleUnpin(fav.path); }}
              title="Unpin"
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <line x1="18" y1="6" x2="6" y2="18" />
                <line x1="6" y1="6" x2="18" y2="18" />
              </svg>
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
