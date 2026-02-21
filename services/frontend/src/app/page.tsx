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
              className={styles.projectCard}
              onClick={() => openProject(project.id)}
            >
              <div className={styles.projectIcon}>
                {project.name[0].toUpperCase()}
              </div>
              <div className={styles.projectInfo}>
                <div className={styles.projectName}>{project.name}</div>
                {project.git_repo_url && (
                  <div className={styles.projectRepo}>{project.git_repo_url}</div>
                )}
                <div className={styles.projectMeta}>
                  {project.member_count} member{project.member_count !== 1 ? "s" : ""}
                  {" \u00B7 "}
                  {project.room_count} room{project.room_count !== 1 ? "s" : ""}
                </div>
              </div>
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
