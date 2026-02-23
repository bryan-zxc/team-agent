# ADR-0006: Workload Session Lifecycle with Worktree Auto-Merge

## Context

Workloads are tasks assigned by Zimomo to AI agents, executed as Claude Code subprocesses via the Claude Agent SDK. Each workload operates on an isolated git worktree so the agent's changes don't affect the main branch until reviewed. The key design questions were: when and how to merge the worktree back, how to handle merge conflicts, and how to support humans resuming a completed workload for further work.

## Alternatives Considered

**System prompt instruction for merge**: Tell the agent to run `git merge` as part of its task. Unreliable — the agent might skip it, do it incorrectly, or get distracted by other work.

**Post-session merge in application code**: After the agent's `ResultMessage`, run the merge as Python code outside the session. Deterministic, but if merge conflicts arise, a new agent session must be spun up specifically for conflict resolution — losing the original session's context of why changes were made.

**SDK Stop hook with conditional session extension**: The chosen approach (see Decision).

## Decision

Use the Claude Agent SDK's `Stop` hook to trigger a deterministic git merge when the agent finishes its turn. The hook runs application-controlled merge logic:

1. Agent completes its task and attempts to stop
2. `Stop` hook fires — our code runs `git merge <worktree-branch>` into main
3. If merge succeeds → clean up worktree, return `continue_: false` (let the agent stop)
4. If merge conflicts → return `continue_: true` with a `systemMessage` describing the conflicts, extending the session so the agent resolves them with full context
5. Max 2 merge-resolve retry cycles. If still failing, give up, keep worktree alive, and set status to `needs_attention`

Starting or resuming a workload session is a single packaged function that:

- **Detects** whether the worktree exists on disk
- If yes → reuse the existing worktree (e.g. agent paused mid-work, or merge failed)
- If no → create a new worktree branched from main (e.g. first run, or resuming after a successful merge cleaned it up)
- Starts or resumes the `ClaudeSDKClient` session — `resume=session_id` preserves conversation context regardless of whether the worktree is new or reused

This decouples conversation context (managed by the SDK via session ID) from filesystem state (managed by our worktree detection logic).

## Consequences

- Merge conflicts are resolved within the agent's original session, preserving full context of why changes were made
- Completed workloads have their changes already on main — no separate merge step for the human
- Humans can resume completed workloads; a new worktree is created transparently while conversation context is preserved
- The Stop hook introduces a retry loop that could theoretically not terminate, mitigated by the 2-retry cap
- Worktree cleanup is tied to successful merge, not to workload status — a `needs_attention` workload may still have a live worktree if merge failed
