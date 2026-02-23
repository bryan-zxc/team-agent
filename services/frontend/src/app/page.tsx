"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import clsx from "clsx";
import { useTheme } from "@/hooks/useTheme";
import { CreateProjectModal } from "@/components/project/CreateProjectModal";
import type { Project, User } from "@/types";
import styles from "./page.module.css";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function LandingPage() {
  const router = useRouter();
  const { theme, toggle } = useTheme();
  const [projects, setProjects] = useState<Project[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [selectedUserId, setSelectedUserId] = useState<string | null>(null);
  const [showUserPicker, setShowUserPicker] = useState(false);
  const [showCreateModal, setShowCreateModal] = useState(false);

  useEffect(() => {
    fetch(`${API_URL}/projects`).then((r) => r.json()).then(setProjects);
    fetch(`${API_URL}/users`).then((r) => r.json()).then(setUsers);
    const stored = localStorage.getItem("user_id");
    if (stored) setSelectedUserId(stored);
  }, []);

  const currentUser = users.find((u) => u.id === selectedUserId);

  const selectUser = useCallback((id: string) => {
    setSelectedUserId(id);
    localStorage.setItem("user_id", id);
    setShowUserPicker(false);
  }, []);

  const openProject = useCallback(
    (projectId: string) => {
      if (!selectedUserId) {
        setShowUserPicker(true);
        return;
      }
      router.push(`/project/${projectId}`);
    },
    [selectedUserId, router],
  );

  const handleProjectCreated = useCallback(
    (project: { id: string }) => {
      router.push(`/project/${project.id}`);
    },
    [router],
  );

  const refreshProject = useCallback(
    async (e: React.MouseEvent, projectId: string) => {
      e.stopPropagation();
      try {
        await fetch(`${API_URL}/projects/${projectId}/check-manifest`, {
          method: "POST",
        });
        const res = await fetch(`${API_URL}/projects`);
        setProjects(await res.json());
      } catch {
        // Silently fail — user can retry
      }
    },
    [],
  );

  return (
    <div className={styles.page}>
      <header className={styles.topBar}>
        <div className={styles.logo}>
          <div className={styles.logoMark}>ta</div>
          <h1 className={styles.logoText}>Team Agent</h1>
        </div>

        <div className={styles.topBarActions}>
          <button className={styles.themeToggle} onClick={toggle} aria-label="Toggle theme">
            {theme === "light" ? "\u263D" : "\u2600"}
          </button>

          <div className={styles.userPickerWrapper}>
            <button
              className={styles.userSelector}
              onClick={() => setShowUserPicker(!showUserPicker)}
            >
              {currentUser ? (
                <>
                  <div className={styles.avatar}>{currentUser.display_name[0]}</div>
                  <span className={styles.userName}>{currentUser.display_name}</span>
                </>
              ) : (
                <span className={styles.userName}>Select user</span>
              )}
              <span className={styles.chevron}>{showUserPicker ? "\u25B2" : "\u25BC"}</span>
            </button>

            {showUserPicker && (
              <div className={styles.userDropdown}>
                {users.map((user) => (
                  <button
                    key={user.id}
                    className={clsx(styles.userOption, user.id === selectedUserId && styles.userOptionActive)}
                    onClick={() => selectUser(user.id)}
                  >
                    <div className={styles.avatar}>{user.display_name[0]}</div>
                    <span>{user.display_name}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      </header>

      <main className={styles.main}>
        <div className={styles.projectsHeader}>
          <h2 className={styles.sectionTitle}>Projects</h2>
          <button
            className={styles.createBtn}
            onClick={() => {
              if (!selectedUserId) {
                setShowUserPicker(true);
                return;
              }
              setShowCreateModal(true);
            }}
          >
            + New Project
          </button>
        </div>

        <div className={styles.projectGrid}>
          {projects.map((project) => (
            <button
              key={project.id}
              className={clsx(styles.projectCard, project.is_locked && styles.projectCardLocked)}
              onClick={() => openProject(project.id)}
            >
              <div className={clsx(styles.projectIcon, project.is_locked && styles.projectIconLocked)}>
                {project.is_locked ? (
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                    <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
                    <path d="M7 11V7a5 5 0 0 1 10 0v4" />
                  </svg>
                ) : (
                  project.name[0].toUpperCase()
                )}
              </div>
              <div className={styles.projectInfo}>
                <div className={styles.projectNameRow}>
                  <span className={styles.projectName}>{project.name}</span>
                  {project.is_locked && (
                    <span className={styles.lockedBadge}>Locked</span>
                  )}
                </div>
                {project.git_repo_url && (
                  <div className={styles.projectRepo}>{project.git_repo_url}</div>
                )}
                <div className={styles.projectMeta}>
                  {project.member_count} member{project.member_count !== 1 ? "s" : ""}
                  {" \u00B7 "}
                  {project.room_count} room{project.room_count !== 1 ? "s" : ""}
                </div>
              </div>
              <button
                className={styles.refreshBtn}
                onClick={(e) => refreshProject(e, project.id)}
                aria-label="Refresh project"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="23 4 23 10 17 10" />
                  <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
                </svg>
              </button>
            </button>
          ))}

          {projects.length === 0 && (
            <div className={styles.emptyState}>
              <p>No projects yet. Create one to get started.</p>
            </div>
          )}
        </div>
      </main>

      <CreateProjectModal
        open={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        onCreated={handleProjectCreated}
      />
    </div>
  );
}
