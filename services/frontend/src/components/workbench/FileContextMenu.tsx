"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import styles from "./FileContextMenu.module.css";

type FileNode = {
  id: string;
  name: string;
  isDirectory: boolean;
};

type FileContextMenuProps = {
  x: number;
  y: number;
  node: FileNode;
  onClose: () => void;
  onCreate: (parentPath: string, name: string, isDir: boolean) => void;
  onDelete: (path: string) => void;
  onRename: (oldPath: string, newName: string) => void;
};

export function FileContextMenu({
  x,
  y,
  node,
  onClose,
  onCreate,
  onDelete,
  onRename,
}: FileContextMenuProps) {
  const menuRef = useRef<HTMLDivElement>(null);
  const [inputMode, setInputMode] = useState<"newFile" | "newFolder" | "rename" | null>(null);
  const [inputValue, setInputValue] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        onClose();
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [onClose]);

  useEffect(() => {
    if (inputMode && inputRef.current) {
      inputRef.current.focus();
      if (inputMode === "rename") {
        inputRef.current.select();
      }
    }
  }, [inputMode]);

  const parentPath = node.isDirectory ? node.id : node.id.substring(0, node.id.lastIndexOf("/")) || "";

  const handleSubmit = useCallback(() => {
    const val = inputValue.trim();
    if (!val) {
      onClose();
      return;
    }
    if (inputMode === "newFile") {
      onCreate(parentPath, val, false);
    } else if (inputMode === "newFolder") {
      onCreate(parentPath, val, true);
    } else if (inputMode === "rename") {
      onRename(node.id, val);
    }
    onClose();
  }, [inputMode, inputValue, parentPath, node.id, onCreate, onRename, onClose]);

  const handleCopyPath = useCallback(() => {
    navigator.clipboard.writeText(node.id);
    onClose();
  }, [node.id, onClose]);

  if (inputMode) {
    return (
      <div ref={menuRef} className={styles.menu} style={{ left: x, top: y }}>
        <div className={styles.inputRow}>
          <input
            ref={inputRef}
            className={styles.input}
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") handleSubmit();
              if (e.key === "Escape") onClose();
            }}
            onBlur={onClose}
            placeholder={inputMode === "rename" ? "New name" : "Name"}
          />
        </div>
      </div>
    );
  }

  return (
    <div ref={menuRef} className={styles.menu} style={{ left: x, top: y }}>
      <button className={styles.item} onClick={() => { setInputValue(""); setInputMode("newFile"); }}>
        New File
      </button>
      <button className={styles.item} onClick={() => { setInputValue(""); setInputMode("newFolder"); }}>
        New Folder
      </button>
      <div className={styles.separator} />
      <button className={styles.item} onClick={() => { setInputValue(node.name); setInputMode("rename"); }}>
        Rename
      </button>
      <button className={styles.itemDanger} onClick={() => { onDelete(node.id); onClose(); }}>
        Delete
      </button>
      <div className={styles.separator} />
      <button className={styles.item} onClick={handleCopyPath}>
        Copy Path
      </button>
    </div>
  );
}
