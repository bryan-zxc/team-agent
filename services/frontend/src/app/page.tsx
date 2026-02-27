"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import clsx from "clsx";
import { useAuth } from "@/hooks/useAuth";
import { useTheme } from "@/hooks/useTheme";
import { apiFetch } from "@/lib/api";
import { CreateProjectModal } from "@/components/project/CreateProjectModal";
import { LandingTerminal } from "@/components/terminal/LandingTerminal";
import type { Project } from "@/types";
import styles from "./page.module.css";

export default function LandingPage() {
  const router = useRouter();
  const { theme, toggle } = useTheme();
  const { user, isLoading, devUsers, login, devLogin, logout } = useAuth();
  const [projects, setProjects] = useState<Project[]>([]);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [terminalOpen, setTerminalOpen] = useState(false);

  useEffect(() => {
    if (!user) return;
    apiFetch("/projects")
      .then((r) => r.json())
      .then(setProjects)
      .catch(() => {});
  }, [user]);

  const openProject = useCallback(
    (projectId: string) => {
      router.push(`/project/${projectId}`);
    },
    [router],
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
        await apiFetch(`/projects/${projectId}/check-manifest`, {
          method: "POST",
        });
        const res = await apiFetch("/projects");
        setProjects(await res.json());
      } catch {
        // Silently fail — user can retry
      }
    },
    [],
  );

  if (isLoading) {
    return (
      <div className={styles.page}>
        <div className={styles.loadingState}>Loading...</div>
      </div>
    );
  }

  // Not authenticated — show login
  if (!user) {
    return (
      <div className={styles.page}>
        <div className={styles.loginContainer}>
          <div className={styles.logoMark}>ta</div>
          <h1 className={styles.loginTitle}>Team Agent</h1>

          <button className={styles.googleBtn} onClick={login}>
            Sign in with Google
          </button>

          {devUsers && devUsers.length > 0 && (
            <div className={styles.devSection}>
              <div className={styles.devDivider}>
                <span>Dev login</span>
              </div>
              <div className={styles.devUserList}>
                {devUsers.map((u) => (
                  <button
                    key={u.id}
                    className={styles.devUserBtn}
                    onClick={() => devLogin(u.id)}
                  >
                    <div className={styles.avatar}>{u.display_name[0]}</div>
                    <span>{u.display_name}</span>
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    );
  }

  // Authenticated — show projects
  return (
    <div className={styles.page}>
      <header className={styles.topBar}>
        <div className={styles.logo}>
          <div className={styles.logoMark}>ta</div>
          <h1 className={styles.logoText}>Team Agent</h1>
        </div>

        <div className={styles.topBarActions}>
          <button className={styles.terminalBtn} onClick={() => setTerminalOpen(!terminalOpen)} aria-label="Toggle terminal" title="Terminal">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="4 17 10 11 4 5" />
              <line x1="12" y1="19" x2="20" y2="19" />
            </svg>
          </button>

          <button className={styles.themeToggle} onClick={toggle} aria-label="Toggle theme">
            {theme === "light" ? "\u263D" : "\u2600"}
          </button>

          <div className={styles.userInfo}>
            {user.avatar_url ? (
              <img
                src={user.avatar_url}
                alt={user.display_name}
                className={styles.avatarImg}
              />
            ) : (
              <div className={styles.avatar}>{user.display_name[0]}</div>
            )}
            <span className={styles.userName}>{user.display_name}</span>
            <button className={styles.logoutBtn} onClick={logout}>
              Sign out
            </button>
          </div>
        </div>
      </header>

      <main className={clsx(styles.main, terminalOpen && styles.mainWithTerminal)}>
        <div className={styles.projectsHeader}>
          <h2 className={styles.sectionTitle}>Projects</h2>
          <button
            className={styles.createBtn}
            onClick={() => setShowCreateModal(true)}
          >
            + New Project
          </button>
        </div>

        <div className={styles.projectGrid}>
          {projects.map((project) => (
            <div
              key={project.id}
              className={clsx(styles.projectCard, project.is_locked && styles.projectCardLocked)}
              onClick={() => openProject(project.id)}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") openProject(project.id); }}
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
            </div>
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

      <LandingTerminal open={terminalOpen} onClose={() => setTerminalOpen(false)} />
    </div>
  );
}
