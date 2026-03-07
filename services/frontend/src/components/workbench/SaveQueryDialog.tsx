"use client";

import clsx from "clsx";
import { useCallback, useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "motion/react";
import { apiFetch } from "@/lib/api";
import styles from "./SaveQueryDialog.module.css";

type TreeNode = {
  path: string;
  name: string;
  isFile: boolean;
  children?: TreeNode[];
  loaded: boolean;
};

type SaveQueryDialogProps = {
  open: boolean;
  projectId: string;
  defaultName?: string;
  onClose: () => void;
  onSave: (path: string) => void;
};

const ROOT_NODE: TreeNode = {
  path: "",
  name: "/ (project root)",
  isFile: false,
  children: undefined,
  loaded: false,
};

async function fetchEntries(projectId: string, path: string): Promise<TreeNode[]> {
  const res = await apiFetch(
    `/projects/${projectId}/files?path=${encodeURIComponent(path)}`,
  );
  if (!res.ok) return [];
  const items: { name: string; type: "file" | "dir"; path: string }[] = await res.json();
  return items
    .filter((item) => item.type === "dir" || item.name.endsWith(".sql"))
    .map((item) => ({
      path: item.path,
      name: item.name,
      isFile: item.type === "file",
      children: item.type === "dir" ? undefined : undefined,
      loaded: item.type === "file",
    }));
}

export function SaveQueryDialog({
  open,
  projectId,
  defaultName = "",
  onClose,
  onSave,
}: SaveQueryDialogProps) {
  const [fileName, setFileName] = useState(defaultName);
  const [selectedFolder, setSelectedFolder] = useState("");
  const [root, setRoot] = useState<TreeNode>(ROOT_NODE);
  const [expanded, setExpanded] = useState<Set<string>>(new Set([""]));
  const [loading, setLoading] = useState(false);
  const [confirmOverwrite, setConfirmOverwrite] = useState(false);
  const pendingPath = useRef<string | null>(null);

  // Load root entries on open
  useEffect(() => {
    if (!open) return;
    setFileName(defaultName);
    setSelectedFolder("");
    setExpanded(new Set([""]));
    setConfirmOverwrite(false);
    pendingPath.current = null;
    setLoading(false);
    fetchEntries(projectId, "").then((children) => {
      setRoot({ ...ROOT_NODE, children, loaded: true });
    });
  }, [open, projectId, defaultName]);

  const handleToggle = useCallback(
    async (node: TreeNode) => {
      if (node.isFile) return;

      if (expanded.has(node.path)) {
        setExpanded((prev) => {
          const next = new Set(prev);
          next.delete(node.path);
          return next;
        });
        return;
      }

      // Load children if not yet loaded
      if (!node.loaded) {
        const children = await fetchEntries(projectId, node.path);
        setRoot((prev) => updateNode(prev, node.path, { children, loaded: true }));
      }

      setExpanded((prev) => new Set(prev).add(node.path));
    },
    [expanded, projectId],
  );

  const handleSelect = useCallback((node: TreeNode) => {
    if (node.isFile) {
      // Clicking a .sql file: populate filename and select its parent folder
      const baseName = node.name.replace(/\.sql$/, "");
      setFileName(baseName);
      const parentPath = node.path.includes("/")
        ? node.path.substring(0, node.path.lastIndexOf("/"))
        : "";
      setSelectedFolder(parentPath);
    } else {
      setSelectedFolder(node.path);
    }
    setConfirmOverwrite(false);
  }, []);

  const handleSubmit = useCallback(async () => {
    const name = fileName.trim();
    if (!name) return;
    const fullName = name.endsWith(".sql") ? name : `${name}.sql`;
    const fullPath = selectedFolder ? `${selectedFolder}/${fullName}` : fullName;

    // If already confirmed, proceed
    if (confirmOverwrite && pendingPath.current === fullPath) {
      setLoading(true);
      onSave(fullPath);
      return;
    }

    // Check if file exists by looking at tree data
    const fileExists = findFileInTree(root, fullPath);
    if (fileExists) {
      pendingPath.current = fullPath;
      setConfirmOverwrite(true);
      return;
    }

    setLoading(true);
    onSave(fullPath);
  }, [fileName, selectedFolder, onSave, root, confirmOverwrite]);

  const previewPath = (() => {
    const name = fileName.trim();
    if (!name) return "";
    const fullName = name.endsWith(".sql") ? name : `${name}.sql`;
    return selectedFolder ? `${selectedFolder}/${fullName}` : fullName;
  })();

  if (!open) return null;

  return (
    <AnimatePresence>
      <motion.div
        className={styles.overlay}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onClick={onClose}
      >
        <motion.div
          className={styles.modal}
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 12 }}
          transition={{ duration: 0.2 }}
          onClick={(e) => e.stopPropagation()}
        >
          <div className={styles.header}>
            <h3 className={styles.title}>Save query</h3>
            <button className={styles.closeBtn} onClick={onClose} aria-label="Close">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <line x1="18" y1="6" x2="6" y2="18" />
                <line x1="6" y1="6" x2="18" y2="18" />
              </svg>
            </button>
          </div>

          <div className={styles.body}>
            <div className={styles.field}>
              <label className={styles.label}>File name</label>
              <div className={styles.filenameRow}>
                <input
                  className={styles.filenameInput}
                  type="text"
                  value={fileName}
                  onChange={(e) => {
                    setFileName(e.target.value);
                    setConfirmOverwrite(false);
                  }}
                  placeholder="query-name"
                  autoFocus
                  onKeyDown={(e) => {
                    if (e.key === "Enter") handleSubmit();
                    if (e.key === "Escape") onClose();
                  }}
                />
                <div className={styles.fileExtension}>.sql</div>
              </div>
            </div>

            <div className={styles.field}>
              <label className={styles.label}>Save to</label>
              <div className={styles.folderTree}>
                <NodeRow
                  node={root}
                  depth={0}
                  expanded={expanded}
                  selectedFolder={selectedFolder}
                  onToggle={handleToggle}
                  onSelect={handleSelect}
                  isRoot
                />
                {expanded.has("") &&
                  root.children?.map((child) => (
                    <NodeBranch
                      key={child.path}
                      node={child}
                      depth={1}
                      expanded={expanded}
                      selectedFolder={selectedFolder}
                      onToggle={handleToggle}
                      onSelect={handleSelect}
                    />
                  ))}
              </div>
            </div>

            {previewPath && (
              <div className={styles.pathPreview}>
                <span>Saving to:</span> {previewPath}
              </div>
            )}

            {confirmOverwrite && (
              <div className={styles.overwriteWarning}>
                A file with this name already exists. Click Save again to overwrite.
              </div>
            )}

            <div className={styles.actions}>
              <button className={styles.cancelBtn} onClick={onClose}>
                Cancel
              </button>
              <button
                className={clsx(
                  styles.saveBtn,
                  confirmOverwrite && styles.saveBtnWarning,
                )}
                onClick={handleSubmit}
                disabled={loading || !fileName.trim()}
              >
                {loading ? "Saving..." : confirmOverwrite ? "Overwrite" : "Save"}
              </button>
            </div>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}

function NodeBranch({
  node,
  depth,
  expanded,
  selectedFolder,
  onToggle,
  onSelect,
}: {
  node: TreeNode;
  depth: number;
  expanded: Set<string>;
  selectedFolder: string;
  onToggle: (node: TreeNode) => void;
  onSelect: (node: TreeNode) => void;
}) {
  const isExpanded = !node.isFile && expanded.has(node.path);
  return (
    <>
      <NodeRow
        node={node}
        depth={depth}
        expanded={expanded}
        selectedFolder={selectedFolder}
        onToggle={onToggle}
        onSelect={onSelect}
      />
      {isExpanded &&
        node.children?.map((child) => (
          <NodeBranch
            key={child.path}
            node={child}
            depth={depth + 1}
            expanded={expanded}
            selectedFolder={selectedFolder}
            onToggle={onToggle}
            onSelect={onSelect}
          />
        ))}
    </>
  );
}

function NodeRow({
  node,
  depth,
  expanded,
  selectedFolder,
  onToggle,
  onSelect,
  isRoot,
}: {
  node: TreeNode;
  depth: number;
  expanded: Set<string>;
  selectedFolder: string;
  onToggle: (node: TreeNode) => void;
  onSelect: (node: TreeNode) => void;
  isRoot?: boolean;
}) {
  const isExpanded = expanded.has(node.path);
  const isSelected = !node.isFile && selectedFolder === node.path;
  const isDir = !node.isFile;
  const hasChildren = isDir && (node.children === undefined || node.children.length > 0);

  return (
    <button
      className={clsx(
        styles.folderItem,
        isSelected && styles.folderItemSelected,
        node.isFile && styles.fileItem,
      )}
      style={{ paddingLeft: 12 + depth * 20 }}
      onClick={() => {
        onSelect(node);
        if (isDir && hasChildren) onToggle(node);
      }}
    >
      {!isRoot && isDir && hasChildren && (
        <svg
          className={clsx(styles.chevron, isExpanded && styles.chevronExpanded)}
          width="14"
          height="14"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <polyline points="9 18 15 12 9 6" />
        </svg>
      )}
      {!isRoot && isDir && !hasChildren && <span className={styles.chevronSpacer} />}
      {node.isFile && <span className={styles.chevronSpacer} />}
      {isRoot ? (
        <svg
          className={styles.rootIcon}
          width="16"
          height="16"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.8"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
          <polyline points="9 22 9 12 15 12 15 22" />
        </svg>
      ) : node.isFile ? (
        <svg
          className={styles.fileIcon}
          width="14"
          height="14"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.8"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
          <polyline points="14 2 14 8 20 8" />
        </svg>
      ) : (
        <svg
          className={styles.folderIcon}
          width="14"
          height="14"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.8"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
        </svg>
      )}
      <span>{node.name}</span>
    </button>
  );
}

function updateNode(
  root: TreeNode,
  targetPath: string,
  updates: Partial<TreeNode>,
): TreeNode {
  if (root.path === targetPath) {
    return { ...root, ...updates };
  }
  if (!root.children) return root;
  return {
    ...root,
    children: root.children.map((child) => updateNode(child, targetPath, updates)),
  };
}

function findFileInTree(node: TreeNode, filePath: string): boolean {
  if (node.isFile && node.path === filePath) return true;
  if (node.children) {
    return node.children.some((child) => findFileInTree(child, filePath));
  }
  return false;
}
