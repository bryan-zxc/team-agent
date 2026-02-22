# ADR-0007: Tool Approval Persistence via Project Settings

## Context

When an AI agent wants to use a tool (e.g. Write, Bash), the human must approve or deny. Repeatedly approving the same tool class is tedious. Claude Code CLI users already have a mechanism for persistent tool approvals: the `allowedTools` array in `.claude/settings.local.json` at the project root. The question was where and how to persist approvals made through the web app.

## Decision

Tool approvals are persisted to `.claude/settings.local.json` in the cloned project repository (e.g. `/data/projects/{id}/repo/.claude/settings.local.json`), using the same format as Claude Code CLI. This makes approvals bidirectional — approvals granted through the web app are visible to CLI users, and vice versa.

Four approval options are presented to the human:

- **Approve** — one-off, this tool call only. No persistence.
- **Approve for session** — stored in-memory for the current workload session. Lost when the session ends.
- **Approve for project** — written to `.claude/settings.local.json`. Persists across all sessions and all users of the project.
- **Deny** — returns the denial with the human's typed reason to the agent inline (no session interrupt). The agent adapts and continues.

The `can_use_tool` callback in the AI service checks project-level settings first (from `.claude/settings.local.json`), then session-level in-memory approvals, before prompting the human.

## Consequences

- CLI users and web app users share a single source of truth for tool permissions
- No custom permissions table needed — the standard Claude Code settings format is reused
- The AI service must have read/write access to the cloned project repo's `.claude/` directory
- Session-scoped approvals are lost on container restart, which is acceptable since they are intentionally ephemeral
- Deny requires a text reason from the human, ensuring the agent understands why and can adapt — this avoids session interruption and worktree lifecycle complications
