"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Tree, type NodeRendererProps } from "react-arborist";
import clsx from "clsx";
import { getFileIcon } from "@/lib/fileIcons";
import { SetiIcon } from "./SetiIcon";
import { apiFetch, uploadFiles } from "@/lib/api";
import { FileContextMenu } from "./FileContextMenu";
import styles from "./FilesSidePanel.module.css";

type FileNode = {
  id: string;
  name: string;
  isDirectory: boolean;
  children?: FileNode[];
};

type FilesSidePanelProps = {
  projectId: string;
  onFileClick: (filePath: string) => void;
};

async function fetchDirectory(projectId: string, path: string): Promise<FileNode[]> {
  const res = await apiFetch(
    `/projects/${projectId}/files?path=${encodeURIComponent(path)}`,
  );
  if (!res.ok) return [];
  const items: { name: string; type: "file" | "dir"; path: string }[] = await res.json();
  return items.map((item) => ({
    id: item.path,
    name: item.name,
    isDirectory: item.type === "dir",
    children: item.type === "dir" ? [] : undefined,
  }));
}

function FileNodeRenderer({ node, style, dragHandle }: NodeRendererProps<FileNode>) {
  return (
    <div
      ref={dragHandle}
      style={style}
      data-node-id={node.data.id}
      className={clsx(styles.node, node.isSelected && styles.nodeSelected)}
      onClick={(e) => {
        e.stopPropagation();
        if (node.isInternal) {
          node.toggle();
        } else {
          node.activate();
        }
      }}
    >
      <span className={styles.nodeToggle}>
        {node.isInternal ? (node.isOpen ? "▾" : "▸") : ""}
      </span>
      {node.data.isDirectory ? (
        <span className={styles.folderIcon}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
            <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
          </svg>
        </span>
      ) : (
        <SetiIcon svg={getFileIcon(node.data.name)} size={16} />
      )}
      <span className={styles.nodeName}>{node.data.name}</span>
      <span className={styles.nodeActions}>
        <button
          className={clsx(styles.actionBtn, styles.deleteBtn)}
          title="Delete"
          onClick={(e) => {
            e.stopPropagation();
            const event = new CustomEvent("file-delete-request", { detail: node.data });
            window.dispatchEvent(event);
          }}
        >
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="3 6 5 6 21 6" /><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" /></svg>
        </button>
      </span>
    </div>
  );
}

export function FilesSidePanel({ projectId, onFileClick }: FilesSidePanelProps) {
  const [data, setData] = useState<FileNode[]>([]);
  const [loading, setLoading] = useState(true);
  const [contextMenu, setContextMenu] = useState<{
    x: number;
    y: number;
    node: FileNode;
  } | null>(null);
  const [uploadProgress, setUploadProgress] = useState<{ loaded: number; total: number } | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [confirmDeleteNode, setConfirmDeleteNode] = useState<FileNode | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const uploadDirRef = useRef("data/raw/");

  useEffect(() => {
    setLoading(true);
    fetchDirectory(projectId, "").then((nodes) => {
      setData(nodes);
      setLoading(false);
    });
  }, [projectId]);

  // Listen for delete requests from memoized tree nodes
  useEffect(() => {
    const handler = (e: Event) => {
      const node = (e as CustomEvent<FileNode>).detail;
      setConfirmDeleteNode(node);
    };
    window.addEventListener("file-delete-request", handler);
    return () => window.removeEventListener("file-delete-request", handler);
  }, []);

  const refreshDirectory = useCallback(
    async (dirPath: string) => {
      const children = await fetchDirectory(projectId, dirPath);
      if (dirPath === "") {
        setData(children);
      } else {
        const updateNodes = (nodes: FileNode[]): FileNode[] =>
          nodes.map((n) =>
            n.id === dirPath ? { ...n, children } : n.children ? { ...n, children: updateNodes(n.children) } : n,
          );
        setData((prev) => updateNodes(prev));
      }
    },
    [projectId],
  );

  const handleToggle = useCallback(
    async (id: string) => {
      const updateChildren = async (nodes: FileNode[]): Promise<FileNode[]> => {
        const result: FileNode[] = [];
        for (const node of nodes) {
          if (node.id === id && node.isDirectory && node.children?.length === 0) {
            const children = await fetchDirectory(projectId, node.id);
            result.push({ ...node, children });
          } else if (node.children) {
            result.push({ ...node, children: await updateChildren(node.children) });
          } else {
            result.push(node);
          }
        }
        return result;
      };
      const updated = await updateChildren(data);
      setData(updated);
    },
    [data, projectId],
  );

  const handleActivate = useCallback(
    (node: { data: FileNode }) => {
      if (!node.data.isDirectory) {
        onFileClick(node.data.id);
      }
    },
    [onFileClick],
  );

  const handleContextMenu = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    const target = (e.target as HTMLElement).closest(`.${styles.node}`) as HTMLElement | null;
    if (!target) return;
    const nodeId = target.dataset.nodeId;
    if (!nodeId) return;

    const findNode = (nodes: FileNode[]): FileNode | null => {
      for (const n of nodes) {
        if (n.id === nodeId) return n;
        if (n.children) {
          const found = findNode(n.children);
          if (found) return found;
        }
      }
      return null;
    };

    const node = findNode(data);
    if (node) {
      setContextMenu({ x: e.clientX, y: e.clientY, node });
    }
  }, [data]);

  const handleCreate = useCallback(
    async (parentPath: string, name: string, isDir: boolean) => {
      const res = await apiFetch(`/projects/${projectId}/files`, {
        method: "POST",
        body: JSON.stringify({ path: parentPath ? `${parentPath}/${name}` : name, is_directory: isDir }),
      });
      if (res.ok) {
        await refreshDirectory(parentPath);
      }
    },
    [projectId, refreshDirectory],
  );

  const handleDelete = useCallback(
    async (path: string) => {
      const res = await apiFetch(
        `/projects/${projectId}/files?path=${encodeURIComponent(path)}`,
        { method: "DELETE" },
      );
      if (res.ok) {
        const parentPath = path.includes("/") ? path.substring(0, path.lastIndexOf("/")) : "";
        await refreshDirectory(parentPath);
      }
    },
    [projectId, refreshDirectory],
  );

  const handleRename = useCallback(
    async (oldPath: string, newName: string) => {
      const res = await apiFetch(`/projects/${projectId}/files`, {
        method: "PATCH",
        body: JSON.stringify({ old_path: oldPath, new_name: newName }),
      });
      if (res.ok) {
        const parentPath = oldPath.includes("/") ? oldPath.substring(0, oldPath.lastIndexOf("/")) : "";
        await refreshDirectory(parentPath);
      }
    },
    [projectId, refreshDirectory],
  );

  const executeDelete = useCallback(() => {
    if (confirmDeleteNode) {
      handleDelete(confirmDeleteNode.id);
      setConfirmDeleteNode(null);
    }
  }, [confirmDeleteNode, handleDelete]);

  const triggerUpload = useCallback(() => {
    uploadDirRef.current = "data/raw/";
    fileInputRef.current?.click();
  }, []);

  const handleUploadToDirectory = useCallback((directory: string) => {
    uploadDirRef.current = directory;
    fileInputRef.current?.click();
  }, []);

  const handleFileSelected = useCallback(
    async (e: React.ChangeEvent<HTMLInputElement>) => {
      const files = e.target.files;
      if (!files || files.length === 0) return;

      setUploadError(null);
      setUploadProgress({ loaded: 0, total: 1 });

      const { promise } = uploadFiles(
        projectId,
        files,
        uploadDirRef.current,
        (loaded, total) => setUploadProgress({ loaded, total }),
      );

      try {
        const result = await promise;
        if (result.errors.length > 0) {
          setUploadError(result.errors.map((e) => `${e.filename}: ${e.detail}`).join(", "));
        }
        // Refresh from root to pick up any newly created intermediate directories
        await refreshDirectory("");
      } catch (err) {
        setUploadError(err instanceof Error ? err.message : "Upload failed");
      } finally {
        setUploadProgress(null);
        // Reset input so re-selecting the same files triggers onChange
        if (fileInputRef.current) fileInputRef.current.value = "";
      }
    },
    [projectId, refreshDirectory],
  );

  const progressPercent = uploadProgress
    ? Math.round((uploadProgress.loaded / uploadProgress.total) * 100)
    : 0;

  return (
    <div className={styles.panel} ref={containerRef} onContextMenu={handleContextMenu}>
      <div className={styles.header}>
        <span className={styles.headerLabel}>Explorer</span>
        <button
          className={styles.uploadBtn}
          onClick={triggerUpload}
          aria-label="Upload files"
          title="Upload files to data/raw/"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
            <polyline points="17 8 12 3 7 8" />
            <line x1="12" y1="3" x2="12" y2="15" />
          </svg>
        </button>
        <input
          ref={fileInputRef}
          type="file"
          multiple
          className={styles.hiddenInput}
          onChange={handleFileSelected}
        />
      </div>

      {uploadProgress && (
        <div className={styles.uploadProgress}>
          <div className={styles.uploadProgressBar} style={{ width: `${progressPercent}%` }} />
          <span className={styles.uploadProgressText}>Uploading... {progressPercent}%</span>
        </div>
      )}

      {uploadError && (
        <div className={styles.uploadError}>{uploadError}</div>
      )}

      {loading ? (
        <div className={styles.loading}>Loading files...</div>
      ) : data.length === 0 ? (
        <div className={styles.empty}>No files found</div>
      ) : (
        <div className={styles.treeWrapper}>
          <Tree
            data={data}
            onToggle={handleToggle}
            onActivate={handleActivate}
            openByDefault={false}
            indent={16}
            rowHeight={28}
            width="100%"
            height={600}
            disableDrag
            disableDrop
          >
            {FileNodeRenderer}
          </Tree>
        </div>
      )}

      {confirmDeleteNode && (
        <div className={styles.confirmOverlay} onClick={() => setConfirmDeleteNode(null)}>
          <div className={styles.confirmDialog} onClick={(e) => e.stopPropagation()}>
            <p className={styles.confirmTitle}>Delete this {confirmDeleteNode.isDirectory ? "folder" : "file"}?</p>
            <p className={styles.confirmPath}>{confirmDeleteNode.id}</p>
            <div className={styles.confirmActions}>
              <button className={styles.confirmCancel} onClick={() => setConfirmDeleteNode(null)}>Cancel</button>
              <button className={styles.confirmDelete} onClick={executeDelete}>Delete</button>
            </div>
          </div>
        </div>
      )}

      {contextMenu && (
        <FileContextMenu
          x={contextMenu.x}
          y={contextMenu.y}
          node={contextMenu.node}
          onClose={() => setContextMenu(null)}
          onCreate={handleCreate}
          onDelete={handleDelete}
          onRename={handleRename}
          onUpload={handleUploadToDirectory}
        />
      )}
    </div>
  );
}
