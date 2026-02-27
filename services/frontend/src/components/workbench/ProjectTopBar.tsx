"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";
import type { Project } from "@/types";
import styles from "./ProjectTopBar.module.css";

type ProjectTopBarProps = {
  project: Project;
  projectId: string;
  onBranchChange: (updatedProject: Project) => void;
};

export function ProjectTopBar({ project, projectId, onBranchChange }: ProjectTopBarProps) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [branches, setBranches] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [switching, setSwitching] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const fetchBranches = useCallback(async () => {
    setLoading(true);
    try {
      const res = await apiFetch(`/projects/${projectId}/branches`);
      if (res.ok) {
        const data = await res.json();
        setBranches(data.branches ?? []);
      }
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  const handleToggle = useCallback(() => {
    if (!open) fetchBranches();
    setOpen((prev) => !prev);
  }, [open, fetchBranches]);

  const handleSwitch = useCallback(async (branch: string) => {
    if (branch === project.default_branch) {
      setOpen(false);
      return;
    }
    setSwitching(true);
    try {
      const res = await apiFetch(`/projects/${projectId}`, {
        method: "PATCH",
        body: JSON.stringify({ default_branch: branch }),
      });
      if (res.ok) {
        const updated = await res.json();
        onBranchChange({ ...project, default_branch: updated.default_branch });
      }
    } catch {
      // silent
    } finally {
      setSwitching(false);
      setOpen(false);
    }
  }, [project, projectId, onBranchChange]);

  // Close dropdown on outside click
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  return (
    <div className={styles.topBar}>
      <span className={styles.projectName}>{project.name}</span>
      <span className={styles.separator}>/</span>

      <div className={styles.branchControl} ref={dropdownRef}>
        <button
          className={styles.branchBtn}
          onClick={handleToggle}
          disabled={switching}
        >
          <svg className={styles.branchIcon} width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="6" y1="3" x2="6" y2="15" />
            <circle cx="18" cy="6" r="3" />
            <circle cx="6" cy="18" r="3" />
            <path d="M18 9a9 9 0 0 1-9 9" />
          </svg>
          {project.default_branch ?? "main"}
          <svg className={styles.chevron} width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="6 9 12 15 18 9" />
          </svg>
        </button>

        {open && (
          <div className={styles.dropdown}>
            {loading ? (
              <div className={styles.dropdownLoading}>Loading branches...</div>
            ) : branches.length === 0 ? (
              <div className={styles.dropdownLoading}>No branches found</div>
            ) : (
              branches.map((b) => (
                <button
                  key={b}
                  className={`${styles.dropdownItem} ${b === project.default_branch ? styles.dropdownItemActive : ""}`}
                  onClick={() => handleSwitch(b)}
                  disabled={switching}
                >
                  <span className={styles.checkMark}>
                    {b === project.default_branch ? "\u2713" : ""}
                  </span>
                  {b}
                </button>
              ))
            )}
          </div>
        )}
      </div>

      <div className={styles.spacer} />
      <button className={styles.backLink} onClick={() => router.push("/")}>
        &larr; Projects
      </button>
    </div>
  );
}
