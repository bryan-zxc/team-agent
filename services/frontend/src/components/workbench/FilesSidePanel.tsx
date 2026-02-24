"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Tree, type NodeRendererProps } from "react-arborist";
import clsx from "clsx";
import { getFileIcon } from "@/lib/fileIcons";
import { SetiIcon } from "./SetiIcon";
import { apiFetch } from "@/lib/api";
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
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setLoading(true);
    fetchDirectory(projectId, "").then((nodes) => {
      setData(nodes);
      setLoading(false);
    });
  }, [projectId]);

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
        const children = await fetchDirectory(projectId, parentPath);
        const updateNodes = (nodes: FileNode[]): FileNode[] =>
          nodes.map((n) =>
            n.id === parentPath ? { ...n, children } : n.children ? { ...n, children: updateNodes(n.children) } : n,
          );
        if (parentPath === "") {
          setData(children);
        } else {
          setData((prev) => updateNodes(prev));
        }
      }
    },
    [projectId],
  );

  const handleDelete = useCallback(
    async (path: string) => {
      const res = await apiFetch(
        `/projects/${projectId}/files?path=${encodeURIComponent(path)}`,
        { method: "DELETE" },
      );
      if (res.ok) {
        const parentPath = path.includes("/") ? path.substring(0, path.lastIndexOf("/")) : "";
        const children = await fetchDirectory(projectId, parentPath);
        const updateNodes = (nodes: FileNode[]): FileNode[] =>
          nodes.map((n) =>
            n.id === parentPath ? { ...n, children } : n.children ? { ...n, children: updateNodes(n.children) } : n,
          );
        if (parentPath === "") {
          setData(children);
        } else {
          setData((prev) => updateNodes(prev));
        }
      }
    },
    [projectId],
  );

  const handleRename = useCallback(
    async (oldPath: string, newName: string) => {
      const res = await apiFetch(`/projects/${projectId}/files`, {
        method: "PATCH",
        body: JSON.stringify({ old_path: oldPath, new_name: newName }),
      });
      if (res.ok) {
        const parentPath = oldPath.includes("/") ? oldPath.substring(0, oldPath.lastIndexOf("/")) : "";
        const children = await fetchDirectory(projectId, parentPath);
        const updateNodes = (nodes: FileNode[]): FileNode[] =>
          nodes.map((n) =>
            n.id === parentPath ? { ...n, children } : n.children ? { ...n, children: updateNodes(n.children) } : n,
          );
        if (parentPath === "") {
          setData(children);
        } else {
          setData((prev) => updateNodes(prev));
        }
      }
    },
    [projectId],
  );

  return (
    <div className={styles.panel} ref={containerRef} onContextMenu={handleContextMenu}>
      <div className={styles.header}>
        <span className={styles.headerLabel}>Explorer</span>
      </div>

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

      {contextMenu && (
        <FileContextMenu
          x={contextMenu.x}
          y={contextMenu.y}
          node={contextMenu.node}
          onClose={() => setContextMenu(null)}
          onCreate={handleCreate}
          onDelete={handleDelete}
          onRename={handleRename}
        />
      )}
    </div>
  );
}
