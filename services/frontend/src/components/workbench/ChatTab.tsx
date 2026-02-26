"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import clsx from "clsx";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { AnimatePresence } from "motion/react";
import { useWebSocket, type TypingEvent } from "@/hooks/useWebSocket";
import type { IDockviewPanelProps } from "dockview";
import type { AgentActivityEvent, Member, Message, Room, Skill, TodoItem, ToolApprovalBlock, WorkloadChat, WorkloadStatusEvent } from "@/types";
import { apiFetch } from "@/lib/api";
import { ToolApprovalCard } from "./ToolApprovalCard";
import { WorkloadPanel } from "./WorkloadPanel";
import { MentionDropdown, filterMembers } from "./MentionDropdown";
import { SlashCommandDropdown, filterSkills } from "./SlashCommandDropdown";
import styles from "./ChatTab.module.css";

type ChatTabParams = {
  roomId: string;
  room: Room;
  memberId: string | null;
  members: Member[];
  projectId: string;
};

function getMessageText(content: string): string {
  try {
    const data = JSON.parse(content);
    if (data?.blocks) {
      return data.blocks
        .map((b: { type: string; value?: string; display_name?: string; name?: string }) => {
          if (b.type === "mention") return `@${b.display_name}`;
          if (b.type === "skill") return `/${b.name}`;
          return b.value ?? "";
        })
        .join("");
    }
  } catch {
    /* legacy plain text */
  }
  return content;
}

function renderMessageContent(content: string): React.ReactNode {
  try {
    const data = JSON.parse(content);
    if (data?.blocks) {
      return data.blocks.map(
        (block: { type: string; value?: string; display_name?: string; name?: string }, i: number) => {
          if (block.type === "mention") {
            return (
              <span key={i} className={styles.mention}>
                @{block.display_name}
              </span>
            );
          }
          if (block.type === "skill") {
            return (
              <span key={i} className={styles.skillTag}>
                /{block.name}
              </span>
            );
          }
          return <span key={i}>{block.value}</span>;
        },
      );
    }
  } catch {
    /* legacy plain text */
  }
  return content;
}

function truncate(text: string, max: number): string {
  return text.length > max ? `${text.slice(0, max)}...` : text;
}

function formatTypingText(members: Map<string, { display_name: string }>): string {
  const names = Array.from(members.values()).map((m) => m.display_name);
  if (names.length === 1) return `${names[0]} is typing...`;
  if (names.length === 2) return `${names[0]} and ${names[1]} are typing...`;
  return `${names[0]} and ${names.length - 1} others are typing...`;
}

function getToolApprovalBlock(content: string): ToolApprovalBlock | null {
  try {
    const data = JSON.parse(content);
    if (data?.blocks?.[0]?.type === "tool_approval_request") {
      return data.blocks[0] as ToolApprovalBlock;
    }
  } catch {
    /* not a tool approval */
  }
  return null;
}

/* ── Rich content block helpers ── */

const SPINNER_VERBS = [
  "Pondering", "Architecting", "Reasoning", "Noodling", "Contemplating",
  "Synthesising", "Deliberating", "Formulating", "Strategising", "Evaluating",
  "Analysing", "Composing", "Cogitating", "Ruminating", "Brainstorming",
];

function pickVerb(): string {
  return SPINNER_VERBS[Math.floor(Math.random() * SPINNER_VERBS.length)];
}

function formatElapsed(ms: number): string {
  const totalSec = Math.floor(ms / 1000);
  const m = Math.floor(totalSec / 60);
  const s = totalSec % 60;
  return `${m}m ${s}s`;
}

function toolUseSummary(name: string, input: Record<string, unknown>): string {
  switch (name) {
    case "Read":
      return `Read ${input.file_path ?? "file"}`;
    case "Bash":
      return `Run: ${truncate(String(input.command ?? ""), 60)}`;
    case "Edit":
      return `Edit ${input.file_path ?? "file"}`;
    case "Write":
      return `Write ${input.file_path ?? "file"}`;
    case "MultiEdit":
      return `Edit ${input.file_path ?? "file"}`;
    case "Grep":
      return `Search for '${input.pattern ?? ""}'`;
    case "Glob":
      return `Find files matching '${input.pattern ?? ""}'`;
    case "WebSearch":
      return `Search web for '${input.query ?? ""}'`;
    case "WebFetch":
      return `Fetch ${truncate(String(input.url ?? ""), 50)}`;
    case "TodoWrite": {
      const todos = Array.isArray(input.todos) ? input.todos : [];
      const done = todos.filter((t: { status: string }) => t.status === "completed").length;
      return `Update tasks (${done} of ${todos.length} completed)`;
    }
    case "TaskCreate":
      return `Create task: ${input.subject ?? ""}`;
    case "TaskUpdate":
      return `Update task ${input.taskId ?? ""}`;
    case "TaskList":
      return "List tasks";
    default:
      return name;
  }
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function renderRichBlocks(blocks: any[]): React.ReactNode {
  return blocks.map((block, i) => {
    switch (block.type) {
      case "text":
        return (
          <div key={i} className={styles.markdownContent}>
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{block.value}</ReactMarkdown>
          </div>
        );
      case "mention":
        return (
          <span key={i} className={styles.mention}>
            @{block.display_name}
          </span>
        );
      case "thinking":
        return (
          <details key={i} className={styles.thinkingBlock}>
            <summary className={styles.thinkingSummary}>Thinking...</summary>
            <div className={styles.thinkingContent}>{block.thinking}</div>
          </details>
        );
      case "tool_use":
        return (
          <details key={i} className={styles.toolUseBlock}>
            <summary className={styles.toolUseSummary}>
              <span className={styles.toolBadge}>{block.name}</span>
              <span>{toolUseSummary(block.name, block.input ?? {})}</span>
            </summary>
            <pre className={styles.toolDetails}>
              {JSON.stringify(block.input, null, 2)}
            </pre>
          </details>
        );
      case "tool_result": {
        const isError = block.is_error === true;
        const content = typeof block.content === "string"
          ? block.content
          : block.content != null
            ? JSON.stringify(block.content, null, 2)
            : "";
        const lines = content.split("\n");
        const isLong = lines.length > 5;
        return (
          <div key={i} className={clsx(styles.toolResultBlock, isError ? styles.toolResultError : styles.toolResultSuccess)}>
            <span className={styles.toolResultIcon}>{isError ? "✕" : "✓"}</span>
            {isLong && !isError ? (
              <details className={styles.toolResultDetails}>
                <summary className={styles.toolResultSummaryLine}>
                  {truncate(lines[0], 80)} ({lines.length} lines)
                </summary>
                <pre className={styles.toolResultContent}>{content}</pre>
              </details>
            ) : content ? (
              <pre className={styles.toolResultContent}>{truncate(content, 500)}</pre>
            ) : null}
          </div>
        );
      }
      default:
        return <span key={i}>{block.value ?? ""}</span>;
    }
  });
}

function renderMsgContent(msg: Message): React.ReactNode {
  if (msg.type === "human") return renderMessageContent(msg.content);
  try {
    const data = JSON.parse(msg.content);
    if (data?.blocks) return renderRichBlocks(data.blocks);
  } catch { /* legacy plain text */ }
  return msg.content;
}

function extractTodos(messages: Message[]): TodoItem[] {
  for (let i = messages.length - 1; i >= 0; i--) {
    try {
      const data = JSON.parse(messages[i].content);
      for (const block of data?.blocks ?? []) {
        if (block.type === "tool_use" && block.name === "TodoWrite" && Array.isArray(block.input?.todos)) {
          return block.input.todos;
        }
      }
    } catch { /* skip */ }
  }
  return [];
}

/* ── ChatView: reusable messages + input for any chat ── */

type ChatViewProps = {
  chatId: string | null;
  memberId: string | null;
  members: Member[];
  projectId: string;
  placeholder: string;
  onAiMessage?: () => void;
  onRoomEvent?: (event: Record<string, unknown>) => void;
  workloadStatus?: string;
  workloadHasSession?: boolean;
  onInterrupt?: () => void;
};

function ChatView({
  chatId,
  memberId,
  members,
  projectId,
  placeholder,
  onAiMessage,
  onRoomEvent,
  workloadStatus,
  workloadHasSession,
  onInterrupt,
}: ChatViewProps) {
  const [input, setInput] = useState("");
  const [resuming, setResuming] = useState(false);
  const [mentionState, setMentionState] = useState<{ query: string; startPos: number } | null>(null);
  const [mentionIndex, setMentionIndex] = useState(0);
  const [commandState, setCommandState] = useState<{ query: string; startPos: number } | null>(null);
  const [commandIndex, setCommandIndex] = useState(0);
  const [skills, setSkills] = useState<Skill[]>([]);
  const [replyTo, setReplyTo] = useState<Message | null>(null);
  const [typingMembers, setTypingMembers] = useState<
    Map<string, { display_name: string; timeout: ReturnType<typeof setTimeout> }>
  >(new Map());
  const [agentActivity, setAgentActivity] = useState<{
    verb: string;
    startTime: number;
    phase: string;
    tokens: number;
    elapsed: number;
  } | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const prevCountRef = useRef(0);
  const prevStatusRef = useRef(workloadStatus);
  const lastTypingRef = useRef(0);

  const handleTypingEvent = useCallback((event: TypingEvent) => {
    setTypingMembers((prev) => {
      const next = new Map(prev);
      const existing = next.get(event.member_id);
      if (existing) clearTimeout(existing.timeout);
      const timeout = setTimeout(() => {
        setTypingMembers((p) => {
          const n = new Map(p);
          n.delete(event.member_id);
          return n;
        });
      }, 5000);
      next.set(event.member_id, { display_name: event.display_name, timeout });
      return next;
    });
  }, []);

  const handleAgentActivity = useCallback((event: AgentActivityEvent) => {
    setAgentActivity((prev) => {
      if (!prev) {
        return { verb: pickVerb(), startTime: Date.now(), phase: event.phase, tokens: event.tokens, elapsed: 0 };
      }
      return { ...prev, phase: event.phase, tokens: event.tokens };
    });
  }, []);

  const { messages, sendMessage, sendTyping, setMessages } = useWebSocket(
    chatId,
    memberId,
    onRoomEvent,
    handleTypingEvent,
    handleAgentActivity,
  );

  useEffect(() => {
    if (!chatId) return;
    apiFetch(`/chats/${chatId}/messages`)
      .then((r) => r.json())
      .then((history: Message[]) => setMessages(history));
  }, [chatId, setMessages]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    if (messages.length > prevCountRef.current) {
      const latest = messages[messages.length - 1];
      if (latest.type !== "human") {
        onAiMessage?.();
        // Clear activity indicator on AI messages and tool approval requests
        // (agent is blocked waiting for human when approval is pending)
        if (latest.type === "tool_approval_request" || latest.type === "ai") {
          setAgentActivity(null);
        }
      }
      // Clear typing indicator when a message arrives from that member
      setTypingMembers((prev) => {
        if (!prev.has(latest.member_id)) return prev;
        const next = new Map(prev);
        const existing = next.get(latest.member_id);
        if (existing) clearTimeout(existing.timeout);
        next.delete(latest.member_id);
        return next;
      });
    }
    prevCountRef.current = messages.length;
  }, [messages, onAiMessage]);

  // Clear resuming state when workload transitions to running
  // Clear agent activity when workload stops running
  useEffect(() => {
    if (prevStatusRef.current !== "running" && workloadStatus === "running") {
      setResuming(false);
    }
    if (prevStatusRef.current === "running" && workloadStatus !== "running") {
      setAgentActivity(null);
    }
    prevStatusRef.current = workloadStatus;
  }, [workloadStatus]);

  // Elapsed timer for agent activity indicator
  const isAgentActive = agentActivity !== null;
  useEffect(() => {
    if (!isAgentActive) return;
    const interval = setInterval(() => {
      setAgentActivity((prev) => prev ? { ...prev, elapsed: Date.now() - prev.startTime } : null);
    }, 1000);
    return () => clearInterval(interval);
  }, [isAgentActive]);

  const todos = useMemo(() => extractTodos(messages), [messages]);
  const [taskPanelOpen, setTaskPanelOpen] = useState(true);
  const completedCount = todos.filter((t) => t.status === "completed").length;

  const memberMap = useMemo(() => new Map(members.map((m) => [m.id, m])), [members]);

  // Exclude self from mentions; in workload chats also exclude other agents
  const mentionableMembers = useMemo(() => {
    let list = members.filter((m) => m.id !== memberId);
    if (workloadStatus !== undefined) {
      list = list.filter((m) => m.type === "human");
    }
    return list;
  }, [members, memberId, workloadStatus]);

  const filteredMentionMembers = useMemo(
    () => (mentionState ? filterMembers(mentionableMembers, mentionState.query) : []),
    [mentionableMembers, mentionState],
  );

  useEffect(() => {
    apiFetch(`/projects/${projectId}/skills`)
      .then((r) => r.json())
      .then(setSkills)
      .catch(() => {});
  }, [projectId]);

  const filteredCommands = useMemo(
    () => (commandState ? filterSkills(skills, commandState.query) : []),
    [skills, commandState],
  );

  const isPaused = workloadStatus === "needs_attention" || workloadStatus === "completed";

  const handleInputChange = useCallback(
    (e: React.ChangeEvent<HTMLTextAreaElement>) => {
      const value = e.target.value;
      const cursorPos = e.target.selectionStart;
      setInput(value);

      // Throttled typing indicator — at most once per 3 seconds
      const now = Date.now();
      if (value.trim() && now - lastTypingRef.current > 3000) {
        sendTyping();
        lastTypingRef.current = now;
      }

      // Scan backwards from cursor for an unmatched @
      const textBeforeCursor = value.slice(0, cursorPos);
      const atIndex = textBeforeCursor.lastIndexOf("@");

      if (atIndex >= 0) {
        const query = textBeforeCursor.slice(atIndex + 1);
        // Mention is valid if no whitespace between @ and cursor, and @ is at start or after whitespace
        if (!query.includes(" ") && !query.includes("\n")) {
          if (atIndex === 0 || /\s/.test(textBeforeCursor[atIndex - 1])) {
            setMentionState({ query, startPos: atIndex });
            setMentionIndex(0);
            setCommandState(null);
            return;
          }
        }
      }

      // Scan backwards from cursor for an unmatched /
      const slashIndex = textBeforeCursor.lastIndexOf("/");
      if (slashIndex >= 0) {
        const query = textBeforeCursor.slice(slashIndex + 1);
        if (!query.includes(" ") && !query.includes("\n")) {
          if (slashIndex === 0 || /\s/.test(textBeforeCursor[slashIndex - 1])) {
            setCommandState({ query, startPos: slashIndex });
            setCommandIndex(0);
            setMentionState(null);
            return;
          }
        }
      }

      setMentionState(null);
      setCommandState(null);
    },
    [sendTyping],
  );

  const handleMentionSelect = useCallback(
    (member: Member) => {
      if (!mentionState) return;
      const before = input.slice(0, mentionState.startPos);
      const after = input.slice(mentionState.startPos + 1 + mentionState.query.length);
      setInput(`${before}@${member.display_name} ${after}`);
      setMentionState(null);
      textareaRef.current?.focus();
    },
    [input, mentionState],
  );

  const handleCommandSelect = useCallback(
    (skill: Skill) => {
      if (!commandState) return;
      const before = input.slice(0, commandState.startPos);
      const after = input.slice(commandState.startPos + 1 + commandState.query.length);
      setInput(`${before}/${skill.name} ${after}`);
      setCommandState(null);
      textareaRef.current?.focus();
    },
    [input, commandState],
  );

  const handleSend = useCallback(() => {
    if (!input.trim()) return;
    const text = input.trim();

    // Build structured blocks: split text at @mention and /skill boundaries
    type Block =
      | { type: "text"; value: string }
      | { type: "mention"; member_id: string; display_name: string }
      | { type: "skill"; name: string };
    const blocks: Block[] = [];
    const mentions: string[] = [];
    let remaining = text;

    while (remaining.length > 0) {
      // Find earliest @mention
      let earliestMentionIdx = -1;
      let earliestMember: Member | null = null;

      for (const member of members) {
        const idx = remaining.toLowerCase().indexOf(`@${member.display_name.toLowerCase()}`);
        if (idx !== -1 && (earliestMentionIdx === -1 || idx < earliestMentionIdx)) {
          earliestMentionIdx = idx;
          earliestMember = member;
        }
      }

      // Find earliest /skill
      let earliestSkillIdx = -1;
      let earliestSkill: Skill | null = null;

      for (const skill of skills) {
        const pattern = `/${skill.name}`;
        const idx = remaining.indexOf(pattern);
        if (idx !== -1 && (earliestSkillIdx === -1 || idx < earliestSkillIdx)) {
          // Ensure /skill is at start or after whitespace, and followed by whitespace or end
          const charAfter = remaining[idx + pattern.length];
          if (
            (idx === 0 || /\s/.test(remaining[idx - 1])) &&
            (charAfter === undefined || /\s/.test(charAfter))
          ) {
            earliestSkillIdx = idx;
            earliestSkill = skill;
          }
        }
      }

      // Determine which comes first
      const mentionFirst = earliestMentionIdx !== -1 && (earliestSkillIdx === -1 || earliestMentionIdx <= earliestSkillIdx);
      const skillFirst = earliestSkillIdx !== -1 && (earliestMentionIdx === -1 || earliestSkillIdx < earliestMentionIdx);

      if (mentionFirst && earliestMember) {
        if (earliestMentionIdx > 0) {
          blocks.push({ type: "text", value: remaining.slice(0, earliestMentionIdx) });
        }
        blocks.push({
          type: "mention",
          member_id: earliestMember.id,
          display_name: earliestMember.display_name,
        });
        if (!mentions.includes(earliestMember.id)) {
          mentions.push(earliestMember.id);
        }
        remaining = remaining.slice(earliestMentionIdx + 1 + earliestMember.display_name.length);
      } else if (skillFirst && earliestSkill) {
        if (earliestSkillIdx > 0) {
          blocks.push({ type: "text", value: remaining.slice(0, earliestSkillIdx) });
        }
        blocks.push({ type: "skill", name: earliestSkill.name });
        remaining = remaining.slice(earliestSkillIdx + 1 + earliestSkill.name.length);
      } else {
        if (remaining) blocks.push({ type: "text", value: remaining });
        break;
      }
    }

    sendMessage(blocks, mentions, replyTo?.id);
    setInput("");
    setReplyTo(null);
    setMentionState(null);
    setCommandState(null);
    if (isPaused && workloadHasSession) {
      setResuming(true);
    }
  }, [input, members, sendMessage, replyTo, isPaused, workloadHasSession]);

  const isRunning = workloadStatus === "running" || workloadStatus === "assigned";

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      // When command dropdown is open, intercept navigation keys
      if (commandState && filteredCommands.length > 0) {
        if (e.key === "ArrowDown") {
          e.preventDefault();
          setCommandIndex((i) => Math.min(i + 1, filteredCommands.length - 1));
          return;
        }
        if (e.key === "ArrowUp") {
          e.preventDefault();
          setCommandIndex((i) => Math.max(i - 1, 0));
          return;
        }
        if (e.key === "Enter" || e.key === "Tab") {
          e.preventDefault();
          handleCommandSelect(filteredCommands[commandIndex]);
          return;
        }
        if (e.key === "Escape") {
          e.preventDefault();
          setCommandState(null);
          return;
        }
      }

      // When mention dropdown is open, intercept navigation keys
      if (mentionState && filteredMentionMembers.length > 0) {
        if (e.key === "ArrowDown") {
          e.preventDefault();
          setMentionIndex((i) => Math.min(i + 1, filteredMentionMembers.length - 1));
          return;
        }
        if (e.key === "ArrowUp") {
          e.preventDefault();
          setMentionIndex((i) => Math.max(i - 1, 0));
          return;
        }
        if (e.key === "Enter" || e.key === "Tab") {
          e.preventDefault();
          handleMentionSelect(filteredMentionMembers[mentionIndex]);
          return;
        }
        if (e.key === "Escape") {
          e.preventDefault();
          setMentionState(null);
          return;
        }
      }

      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
      if (e.key === "Escape" && isRunning && onInterrupt) {
        e.preventDefault();
        if (input.trim()) {
          setInput("");
        } else {
          onInterrupt();
        }
      }
    },
    [handleSend, isRunning, onInterrupt, input, mentionState, filteredMentionMembers, mentionIndex, handleMentionSelect, commandState, filteredCommands, commandIndex, handleCommandSelect],
  );

  const scrollToMessage = useCallback((messageId: string) => {
    const el = document.getElementById(`msg-${messageId}`);
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "center" });
      el.classList.add(styles.highlighted);
      setTimeout(() => el.classList.remove(styles.highlighted), 1500);
    }
  }, []);

  const formatTime = (iso: string) => {
    const d = new Date(iso);
    return d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  };

  return (
    <div className={styles.chatView}>
      {workloadStatus !== undefined && todos.length > 0 && (
        <div className={styles.taskPanel}>
          <button className={styles.taskPanelHeader} onClick={() => setTaskPanelOpen((p) => !p)}>
            <div className={styles.taskPanelHeaderLeft}>
              <span className={styles.taskPanelLabel}>Tasks</span>
              <span className={styles.taskPanelCount}>{completedCount} of {todos.length}</span>
            </div>
            <div className={styles.taskPanelProgress}>
              <div className={styles.progressBar}>
                <div className={styles.progressFill} style={{ width: `${(completedCount / todos.length) * 100}%` }} />
              </div>
              <span className={clsx(styles.chevron, taskPanelOpen && styles.chevronOpen)}>&#x25BC;</span>
            </div>
          </button>
          {taskPanelOpen && (
            <div className={styles.taskList}>
              {todos.map((todo, i) => (
                <div key={i} className={styles.taskItem}>
                  <span className={clsx(styles.taskIcon, styles[`taskIcon_${todo.status}` as keyof typeof styles])} />
                  <span className={clsx(styles.taskContent, todo.status === "completed" && styles.taskContentCompleted, todo.status === "in_progress" && styles.taskContentActive)}>
                    {todo.content}
                  </span>
                  {todo.status === "in_progress" && todo.activeForm && (
                    <span className={styles.taskActiveForm}>{todo.activeForm}</span>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
      <div className={styles.messages}>
        {messages.map((msg) => {
          // Tool approval request — detect from content (type may be "ai" when loaded from API)
          const approvalBlock = getToolApprovalBlock(msg.content);
          if (approvalBlock) {
            return (
              <div key={msg.id} className={styles.approvalRow}>
                <ToolApprovalCard block={approvalBlock} disabled={!!workloadStatus && !isRunning} />
              </div>
            );
          }

          const isSelf = msg.member_id === memberId;
          const isAi = msg.type !== "human";
          const replyParent = msg.reply_to_id
            ? messages.find((m) => m.id === msg.reply_to_id)
            : null;

          return (
            <div
              key={msg.id}
              id={`msg-${msg.id}`}
              className={clsx(styles.messageGroup, isSelf && styles.self, isAi && styles.ai)}
            >
              <div className={clsx(styles.msgAvatar, isAi ? styles.avatarAi : styles.avatarHuman)}>
                {msg.display_name[0]}
              </div>
              <div className={styles.msgBody}>
                <div className={styles.msgHeader}>
                  <span className={styles.msgAuthor}>{msg.display_name}</span>
                  {isAi && <span className={styles.aiBadge}>AI</span>}
                  <span className={styles.msgTime}>{formatTime(msg.created_at)}</span>
                </div>
                {replyParent && (
                  <button
                    className={styles.replyRef}
                    onClick={() => scrollToMessage(replyParent.id)}
                  >
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <polyline points="9 14 4 9 9 4" />
                      <path d="M20 20v-7a4 4 0 0 0-4-4H4" />
                    </svg>
                    <span className={styles.replyRefAuthor}>{replyParent.display_name}</span>
                    <span className={styles.replyRefText}>
                      {truncate(getMessageText(replyParent.content), 60)}
                    </span>
                  </button>
                )}
                <div className={styles.msgBubble}>{renderMsgContent(msg)}</div>
                <button
                  className={styles.replyBtn}
                  onClick={() => {
                    setReplyTo(msg);
                    textareaRef.current?.focus();
                  }}
                  aria-label="Reply"
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <polyline points="9 14 4 9 9 4" />
                    <path d="M20 20v-7a4 4 0 0 0-4-4H4" />
                  </svg>
                </button>
              </div>
            </div>
          );
        })}
        <div ref={messagesEndRef} />
      </div>

      {agentActivity && (
        <div className={styles.agentStatus}>
          <span className={styles.spinner} />
          <span className={styles.agentVerb}>{agentActivity.verb}...</span>
          <span className={styles.agentMeta}>
            ({formatElapsed(agentActivity.elapsed)} · {agentActivity.tokens} tokens)
          </span>
        </div>
      )}

      {typingMembers.size > 0 && (
        <div className={styles.typingIndicator}>
          <span className={styles.typingDots}>
            <span />
            <span />
            <span />
          </span>
          <span>{formatTypingText(typingMembers)}</span>
        </div>
      )}

      {workloadStatus && !isRunning && (
        <div className={styles.statusBanner}>
          {resuming ? (
            <>
              <span className={styles.statusDot} />
              <span>Resuming session...</span>
            </>
          ) : isPaused && workloadHasSession ? (
            <span>Agent paused — send a message to resume</span>
          ) : isPaused && !workloadHasSession ? (
            <span>Agent session ended</span>
          ) : null}
        </div>
      )}

      <div className={styles.inputArea}>
        {replyTo && (
          <div className={styles.replyPreview}>
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="9 14 4 9 9 4" />
              <path d="M20 20v-7a4 4 0 0 0-4-4H4" />
            </svg>
            <span className={styles.replyPreviewAuthor}>{replyTo.display_name}</span>
            <span className={styles.replyPreviewText}>
              {truncate(getMessageText(replyTo.content), 80)}
            </span>
            <button
              className={styles.replyPreviewClose}
              onClick={() => setReplyTo(null)}
              aria-label="Cancel reply"
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <line x1="18" y1="6" x2="6" y2="18" />
                <line x1="6" y1="6" x2="18" y2="18" />
              </svg>
            </button>
          </div>
        )}
        <div className={styles.inputWrapper}>
          <AnimatePresence>
            {mentionState && filteredMentionMembers.length > 0 && (
              <MentionDropdown
                members={filteredMentionMembers}
                query={mentionState.query}
                selectedIndex={mentionIndex}
                onSelect={handleMentionSelect}
              />
            )}
            {commandState && filteredCommands.length > 0 && (
              <SlashCommandDropdown
                skills={filteredCommands}
                query={commandState.query}
                selectedIndex={commandIndex}
                onSelect={handleCommandSelect}
              />
            )}
          </AnimatePresence>
          <textarea
            ref={textareaRef}
            className={styles.inputField}
            placeholder={placeholder}
            value={input}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
            rows={1}
          />
          {isRunning && onInterrupt && (
            <button
              className={styles.interruptBtn}
              onClick={onInterrupt}
              aria-label="Interrupt workload"
              title="Interrupt (Esc)"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <rect x="6" y="6" width="12" height="12" rx="2" />
              </svg>
            </button>
          )}
          <button className={styles.sendBtn} onClick={handleSend} aria-label="Send message">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <line x1="22" y1="2" x2="11" y2="13" />
              <polygon points="22 2 15 22 11 13 2 9 22 2" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
}

/* ── ChatTab: dockview panel with dynamic internal tabs ── */

export function ChatTab({ params }: IDockviewPanelProps<ChatTabParams>) {
  const { roomId, room, memberId, members, projectId } = params;
  const [workloads, setWorkloads] = useState<WorkloadChat[]>([]);
  const [activeChatId, setActiveChatId] = useState<string>(room.primary_chat_id);
  const [panelOpen, setPanelOpen] = useState(false);

  const refreshWorkloads = useCallback(() => {
    apiFetch(`/rooms/${roomId}/workloads`)
      .then((r) => r.json())
      .then((data: WorkloadChat[]) => setWorkloads(data))
      .catch(() => {});
  }, [roomId]);

  useEffect(() => {
    refreshWorkloads();
  }, [refreshWorkloads]);

  const handleRoomEvent = useCallback(
    (event: Record<string, unknown>) => {
      if (event._event === "workload_status") {
        const e = event as unknown as WorkloadStatusEvent;
        setWorkloads((prev) => {
          const idx = prev.findIndex((w) => w.workload_id === e.workload_id);
          if (idx === -1) {
            // New workload — re-fetch to get full data
            refreshWorkloads();
            return prev;
          }
          const updated = [...prev];
          updated[idx] = { ...updated[idx], status: e.status, updated_at: e.updated_at };
          return updated;
        });
      }
    },
    [refreshWorkloads],
  );

  const handleCancel = useCallback(
    async (workloadId: string) => {
      // Optimistic update
      setWorkloads((prev) =>
        prev.map((w) =>
          w.workload_id === workloadId
            ? { ...w, status: "cancelled", updated_at: new Date().toISOString() }
            : w,
        ),
      );
      try {
        const resp = await apiFetch(`/workloads/${workloadId}/cancel`, {
          method: "POST",
        });
        if (!resp.ok) refreshWorkloads();
      } catch {
        refreshWorkloads();
      }
    },
    [refreshWorkloads],
  );

  const handleComplete = useCallback(
    async (workloadId: string) => {
      // Optimistic update
      setWorkloads((prev) =>
        prev.map((w) =>
          w.workload_id === workloadId
            ? { ...w, status: "completed", updated_at: new Date().toISOString() }
            : w,
        ),
      );
      try {
        const resp = await apiFetch(`/workloads/${workloadId}`, {
          method: "PATCH",
          body: JSON.stringify({ status: "completed" }),
        });
        if (!resp.ok) refreshWorkloads();
      } catch {
        refreshWorkloads();
      }
    },
    [refreshWorkloads],
  );

  const handleInterrupt = useCallback(
    async (workloadId: string) => {
      setWorkloads((prev) =>
        prev.map((w) =>
          w.workload_id === workloadId
            ? { ...w, status: "needs_attention", updated_at: new Date().toISOString() }
            : w,
        ),
      );
      try {
        const resp = await apiFetch(`/workloads/${workloadId}/interrupt`, {
          method: "POST",
        });
        if (!resp.ok) refreshWorkloads();
      } catch {
        refreshWorkloads();
      }
    },
    [refreshWorkloads],
  );

  // Find workload for the active chat (if viewing a workload chat)
  const activeWorkload = workloads.find((w) => w.id === activeChatId);

  const hasWorkloads = workloads.length > 0;

  return (
    <div className={styles.container}>
      <div className={styles.tabs}>
        <button
          className={clsx(styles.tab, activeChatId === room.primary_chat_id && styles.tabActive)}
          onClick={() => setActiveChatId(room.primary_chat_id)}
        >
          Main
        </button>
        {workloads.map((w) => (
          <button
            key={w.id}
            className={clsx(styles.tab, activeChatId === w.id && styles.tabActive)}
            onClick={() => setActiveChatId(w.id)}
          >
            {w.owner_name}: {w.title}
          </button>
        ))}
        <button
          className={clsx(styles.panelToggle, panelOpen && styles.panelToggleActive)}
          onClick={() => setPanelOpen((p) => !p)}
          aria-label="Toggle workload panel"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
            <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
            <line x1="15" y1="3" x2="15" y2="21" />
          </svg>
        </button>
      </div>

      <div className={styles.body}>
        <ChatView
          key={activeChatId}
          chatId={activeChatId}
          memberId={memberId}
          members={members}
          projectId={projectId}
          placeholder={`Message ${room.name}...`}
          onAiMessage={activeChatId === room.primary_chat_id ? refreshWorkloads : undefined}
          onRoomEvent={handleRoomEvent}
          workloadStatus={activeWorkload?.status}
          workloadHasSession={activeWorkload?.has_session}
          onInterrupt={
            activeWorkload
              ? () => handleInterrupt(activeWorkload.workload_id)
              : undefined
          }
        />
        <div className={clsx(styles.panel, !panelOpen && styles.panelCollapsed)}>
          {panelOpen && (
            <WorkloadPanel
              workloads={workloads}
              activeChatId={activeChatId}
              onSelectWorkload={setActiveChatId}
              onCancel={handleCancel}
              onComplete={handleComplete}
              onInterrupt={handleInterrupt}
            />
          )}
        </div>
      </div>
    </div>
  );
}
