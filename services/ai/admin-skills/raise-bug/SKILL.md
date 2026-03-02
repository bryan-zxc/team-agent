---
name: raise-bug
description: Investigate, diagnose, and file a bug ticket with full context for debugging and resolution. Use this skill whenever you encounter unexpected behaviour, errors, crashes, or anything that used to work but is now broken. Triggers on any mention of bug, error, crash, regression, broken behaviour, unexpected result, or "this shouldn't happen".
---

# Raise Bug

Investigate a bug, gather evidence from the diagnostics API, and file a detailed ticket on GitHub. The goal is that a developer picking up the ticket can diagnose and fix the issue without starting from scratch.

## Your environment

You are running inside the AI service container. Here is what you have:

- **Diagnostics API** — logs, chat/workload state, rooms, projects. Read `references/diagnostics-api.md` for the full endpoint reference with examples.
- **File system** at `/data/projects/` — cloned user project repos (for checking git state, worktrees, locks)
- **`gh` CLI** — for filing tickets on GitHub

You do **not** have access to the application source code. The repos at `/data/projects/` are user projects (e.g. a dashboard app, a storefront) — they are not the Team Agent codebase. Do not try to read source files, grep for code patterns, explore directories looking for frontend/backend code, or trace code paths. That code is not in your environment. Diagnose purely from the evidence the diagnostics API provides.

You also do not have direct database access. Do not use `psql` or attempt database connections. All data access goes through the diagnostics API endpoints.

## Step 1: Gather evidence

Read `references/diagnostics-api.md` for full endpoint details. The typical investigation flow:

1. **Discover rooms and chats** — start with `GET /diagnostics/rooms` and `GET /diagnostics/chats` to find the relevant entities. You usually won't know chat IDs upfront, so search by status, type, or room.

2. **Get full context** — once you've identified the relevant chat, fetch `GET /diagnostics/chats/{chat_id}` for the complete picture: chat record, workload, room, project, owner, and recent messages.

3. **Check logs** — pull error logs from both services with `GET /diagnostics/logs?level=ERROR`. Cross-reference timestamps with the chat timeline.

4. **Check git state** — if the bug involves git operations, inspect the clone at the path from the diagnostics response (`project.clone_path`):
   ```bash
   git -C <clone_path> worktree list
   ls -la <clone_path>/.git/worktrees/
   df -h /data/projects
   ```

## Step 2: Analyse

Before filing, make sense of the evidence:

1. **Correlate timestamps** — match error log entries with chat events and status transitions to reconstruct the sequence of events
2. **Identify the root cause** if the evidence points to one — a state stuck in the wrong status, a failed operation that wasn't cleaned up, a missing transition
3. **Document reproduction steps** — starting state, numbered actions, expected vs actual result

If the bug is intermittent and you can't piece together a reproduction, document what you observed and the conditions.

## Step 3: File the ticket

Read `references/github-board.md` for the ticket template and board commands. Create the issue, add it to project board 3, and set the status to Backlog.

Before filing, check that your ticket has:

- A title that describes the **symptom** from the user's perspective
- Actual log excerpts with timestamps (not paraphrases)
- Diagnostics output showing the state at time of failure
- Reproduction steps (or explanation of why not reproducible)
- Root cause analysis if you've identified one from the evidence
