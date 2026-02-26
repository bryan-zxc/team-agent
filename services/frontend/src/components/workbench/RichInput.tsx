"use client";

import {
  forwardRef,
  useCallback,
  useImperativeHandle,
  useRef,
} from "react";
import clsx from "clsx";
import type { Member, Skill } from "@/types";
import chatStyles from "./ChatTab.module.css";
import styles from "./RichInput.module.css";

/* ── Public types ── */

export type Block =
  | { type: "text"; value: string }
  | { type: "mention"; member_id: string; display_name: string }
  | { type: "skill"; name: string };

export type TriggerState = {
  type: "mention" | "command";
  query: string;
};

export type RichInputHandle = {
  focus: () => void;
  clear: () => void;
  isEmpty: () => boolean;
  getBlocks: () => Block[];
  getMentionIds: () => string[];
  insertMentionChip: (member: Member) => void;
  insertSkillChip: (skill: Skill) => void;
};

type Props = {
  placeholder?: string;
  className?: string;
  onTriggerChange: (trigger: TriggerState | null) => void;
  onKeyDown: (e: React.KeyboardEvent<HTMLDivElement>) => void;
  onTyping: () => void;
};

/* ── Constants ── */

const ZWSP = "\u200B";

/* ── Helpers ── */

function detectTrigger(): { type: "mention" | "command"; query: string; range: Range } | null {
  const sel = window.getSelection();
  if (!sel || sel.rangeCount === 0 || !sel.isCollapsed) return null;

  const { anchorNode, anchorOffset } = sel;
  if (!anchorNode || anchorNode.nodeType !== Node.TEXT_NODE) return null;

  const text = anchorNode.textContent ?? "";
  const before = text.slice(0, anchorOffset);

  // Try @ mention
  const atIdx = before.lastIndexOf("@");
  if (atIdx >= 0) {
    const query = before.slice(atIdx + 1);
    if (!query.includes(" ") && !query.includes("\n")) {
      if (atIdx === 0 || /\s/.test(before[atIdx - 1])) {
        const range = document.createRange();
        range.setStart(anchorNode, atIdx);
        range.setEnd(anchorNode, anchorOffset);
        return { type: "mention", query, range };
      }
    }
  }

  // Try / command
  const slashIdx = before.lastIndexOf("/");
  if (slashIdx >= 0) {
    const query = before.slice(slashIdx + 1);
    if (!query.includes(" ") && !query.includes("\n")) {
      if (slashIdx === 0 || /\s/.test(before[slashIdx - 1])) {
        const range = document.createRange();
        range.setStart(anchorNode, slashIdx);
        range.setEnd(anchorNode, anchorOffset);
        return { type: "command", query, range };
      }
    }
  }

  return null;
}

function createChipSpan(
  type: "mention" | "skill",
  attrs: Record<string, string>,
  label: string,
  className: string,
): HTMLSpanElement {
  const span = document.createElement("span");
  span.contentEditable = "false";
  span.dataset.type = type;
  for (const [k, v] of Object.entries(attrs)) {
    span.dataset[k] = v;
  }
  span.className = className;
  span.textContent = label;
  return span;
}

function insertChipAtRange(range: Range, chip: HTMLSpanElement) {
  // Delete the trigger text
  range.deleteContents();

  // Insert chip
  range.insertNode(chip);

  // Insert trailing spacer for caret placement
  const spacer = document.createTextNode(`${ZWSP} `);
  chip.after(spacer);

  // Move caret after spacer
  const sel = window.getSelection();
  if (sel) {
    const newRange = document.createRange();
    newRange.setStartAfter(spacer);
    newRange.collapse(true);
    sel.removeAllRanges();
    sel.addRange(newRange);
  }
}

function serialiseBlocks(editor: HTMLDivElement): { blocks: Block[]; mentions: string[] } {
  const blocks: Block[] = [];
  const mentions: string[] = [];

  function walkNodes(parent: Node) {
    for (const node of parent.childNodes) {
      if (node.nodeType === Node.TEXT_NODE) {
        const text = (node.textContent ?? "").replace(/\u200B/g, "");
        if (text) blocks.push({ type: "text", value: text });
      } else if (node instanceof HTMLElement) {
        if (node.dataset.type === "mention") {
          const memberId = node.dataset.memberId!;
          const displayName = node.dataset.displayName!;
          blocks.push({ type: "mention", member_id: memberId, display_name: displayName });
          if (!mentions.includes(memberId)) mentions.push(memberId);
        } else if (node.dataset.type === "skill") {
          blocks.push({ type: "skill", name: node.dataset.name! });
        } else if (node.tagName === "BR") {
          const last = blocks[blocks.length - 1];
          if (last && last.type === "text") {
            last.value += "\n";
          } else {
            blocks.push({ type: "text", value: "\n" });
          }
        } else if (node.tagName === "DIV") {
          // Browsers wrap lines in <div> — treat as newline-separated
          const last = blocks[blocks.length - 1];
          if (last && last.type === "text" && !last.value.endsWith("\n")) {
            last.value += "\n";
          } else if (blocks.length > 0 && blocks[blocks.length - 1]?.type !== "text") {
            blocks.push({ type: "text", value: "\n" });
          }
          walkNodes(node);
        }
      }
    }
  }

  walkNodes(editor);

  // Merge adjacent text blocks
  const merged: Block[] = [];
  for (const block of blocks) {
    const prev = merged[merged.length - 1];
    if (block.type === "text" && prev && prev.type === "text") {
      prev.value += block.value;
    } else {
      merged.push(block);
    }
  }

  // Trim leading/trailing whitespace on outer text blocks
  if (merged.length > 0 && merged[0].type === "text") {
    merged[0].value = merged[0].value.replace(/^\s+/, "");
  }
  const last = merged[merged.length - 1];
  if (last && last.type === "text") {
    last.value = last.value.replace(/\s+$/, "");
  }

  return {
    blocks: merged.filter((b) => b.type !== "text" || b.value),
    mentions,
  };
}

function isEditorEmpty(editor: HTMLDivElement): boolean {
  const text = (editor.textContent ?? "").replace(/\u200B/g, "").trim();
  return text === "" && editor.querySelectorAll("[data-type]").length === 0;
}

/* ── Component ── */

export const RichInput = forwardRef<RichInputHandle, Props>(
  function RichInput({ placeholder, className, onTriggerChange, onKeyDown, onTyping }, ref) {
    const editorRef = useRef<HTMLDivElement>(null);
    const triggerRangeRef = useRef<Range | null>(null);
    const composingRef = useRef(false);

    const updateEmptyClass = useCallback(() => {
      const el = editorRef.current;
      if (!el) return;
      if (isEditorEmpty(el)) {
        el.classList.add(styles.empty);
      } else {
        el.classList.remove(styles.empty);
      }
    }, []);

    const handleInput = useCallback(() => {
      const el = editorRef.current;
      if (!el) return;

      updateEmptyClass();
      onTyping();

      // Skip trigger detection during IME composition
      if (composingRef.current) return;

      const trigger = detectTrigger();
      if (trigger) {
        triggerRangeRef.current = trigger.range;
        onTriggerChange({ type: trigger.type, query: trigger.query });
      } else {
        triggerRangeRef.current = null;
        onTriggerChange(null);
      }
    }, [onTriggerChange, onTyping, updateEmptyClass]);

    const handlePaste = useCallback((e: React.ClipboardEvent<HTMLDivElement>) => {
      e.preventDefault();
      const text = e.clipboardData.getData("text/plain");
      if (text) {
        document.execCommand("insertText", false, text);
      }
    }, []);

    const handleBeforeInput = useCallback((e: React.FormEvent<HTMLDivElement>) => {
      const inputEvent = e.nativeEvent as InputEvent;

      if (inputEvent.inputType === "deleteContentBackward") {
        const sel = window.getSelection();
        if (!sel || !sel.isCollapsed) return;

        const { anchorNode, anchorOffset } = sel;
        if (!anchorNode) return;

        // Case 1: caret at start of a text node that follows a chip
        if (anchorNode.nodeType === Node.TEXT_NODE && anchorOffset === 0) {
          const prev = anchorNode.previousSibling;
          if (prev instanceof HTMLElement && prev.dataset.type) {
            e.preventDefault();
            prev.remove();
            updateEmptyClass();
            return;
          }
        }

        // Case 2: caret at offset <= 1 in ZWSP text node after a chip
        if (
          anchorNode.nodeType === Node.TEXT_NODE &&
          anchorOffset <= 1 &&
          anchorNode.textContent?.[0] === ZWSP
        ) {
          const prev = anchorNode.previousSibling;
          if (prev instanceof HTMLElement && prev.dataset.type) {
            e.preventDefault();
            prev.remove();
            // Remove the ZWSP character
            if (anchorNode.textContent) {
              anchorNode.textContent = anchorNode.textContent.slice(1);
            }
            updateEmptyClass();
            return;
          }
        }
      }
    }, [updateEmptyClass]);

    const handleCopy = useCallback((e: React.ClipboardEvent<HTMLDivElement>) => {
      const sel = window.getSelection();
      if (!sel || sel.rangeCount === 0) return;
      const text = sel.toString();
      e.clipboardData.setData("text/plain", text);
      e.preventDefault();
    }, []);

    const handleKeyDownInternal = useCallback(
      (e: React.KeyboardEvent<HTMLDivElement>) => {
        // Let parent handle first (dropdown nav, Enter to send, etc.)
        onKeyDown(e);
      },
      [onKeyDown],
    );

    useImperativeHandle(ref, () => ({
      focus() {
        const el = editorRef.current;
        if (!el) return;
        el.focus();
        // Place caret at end
        const sel = window.getSelection();
        if (sel) {
          sel.selectAllChildren(el);
          sel.collapseToEnd();
        }
      },

      clear() {
        const el = editorRef.current;
        if (!el) return;
        el.innerHTML = "";
        el.classList.add(styles.empty);
        triggerRangeRef.current = null;
        onTriggerChange(null);
      },

      isEmpty() {
        return editorRef.current ? isEditorEmpty(editorRef.current) : true;
      },

      getBlocks() {
        if (!editorRef.current) return [];
        return serialiseBlocks(editorRef.current).blocks;
      },

      getMentionIds() {
        if (!editorRef.current) return [];
        return serialiseBlocks(editorRef.current).mentions;
      },

      insertMentionChip(member: Member) {
        const range = triggerRangeRef.current;
        if (!range || !editorRef.current) return;
        const chip = createChipSpan(
          "mention",
          { memberId: member.id, displayName: member.display_name },
          `@${member.display_name}`,
          chatStyles.mention,
        );
        insertChipAtRange(range, chip);
        triggerRangeRef.current = null;
        onTriggerChange(null);
        updateEmptyClass();
      },

      insertSkillChip(skill: Skill) {
        const range = triggerRangeRef.current;
        if (!range || !editorRef.current) return;
        const chip = createChipSpan(
          "skill",
          { name: skill.name },
          `/${skill.name}`,
          chatStyles.skillTag,
        );
        insertChipAtRange(range, chip);
        triggerRangeRef.current = null;
        onTriggerChange(null);
        updateEmptyClass();
      },
    }), [onTriggerChange, updateEmptyClass]);

    return (
      <div
        ref={editorRef}
        className={clsx(styles.richInput, styles.empty, className)}
        contentEditable
        role="textbox"
        aria-multiline
        data-placeholder={placeholder}
        onInput={handleInput}
        onKeyDown={handleKeyDownInternal}
        onPaste={handlePaste}
        onBeforeInput={handleBeforeInput}
        onCopy={handleCopy}
        onCompositionStart={() => { composingRef.current = true; }}
        onCompositionEnd={() => {
          composingRef.current = false;
          // Re-run trigger detection after composition ends
          handleInput();
        }}
        suppressContentEditableWarning
      />
    );
  },
);
