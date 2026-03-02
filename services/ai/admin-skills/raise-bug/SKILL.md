---
name: raise-bug
description: Investigate, diagnose, and file a bug ticket with full context for debugging and resolution. Use this skill whenever you encounter unexpected behaviour, errors, crashes, or anything that used to work but is now broken. Triggers on any mention of bug, error, crash, regression, broken behaviour, unexpected result, or "this shouldn't happen".
---

# Raise Bug

When you encounter a bug — something broken, an unexpected error, a regression — investigate thoroughly, gather all the evidence, and file a richly detailed ticket. The goal is that a future session can diagnose and fix the issue without starting from scratch.

## Step 1: Gather Evidence

Collect as much diagnostic context as possible before filing anything.

### Application logs

Pull recent error logs from both services via their diagnostics endpoints:

```bash
# AI service errors (last 200 entries)
curl -s 'http://ai-service:8001/diagnostics/logs?level=ERROR&limit=200' | python3 -m json.tool

# API service errors
curl -s 'http://api:8000/diagnostics/logs?level=ERROR&limit=200' | python3 -m json.tool

# Warnings too, if errors are sparse
curl -s 'http://ai-service:8001/diagnostics/logs?level=WARNING&limit=100' | python3 -m json.tool

# Filter by time window (ISO 8601)
curl -s 'http://ai-service:8001/diagnostics/logs?since=2026-03-02T00:00:00Z&limit=200' | python3 -m json.tool
```

### Chat and workload context

If the bug involves a specific chat or workload, fetch the full diagnostic view:

```bash
curl -s 'http://api:8000/diagnostics/chats/<chat_id>' | python3 -m json.tool
```

This returns the chat record, its workload, room, project, owner, and recent messages — everything needed to understand the state at the time of the bug.

### File system state

Check directly on disk — you have access to `/data/projects/`:

```bash
# Worktree status
git -C /data/projects/<project-dir> worktree list

# Check for stale locks or corrupt state
ls -la /data/projects/<project-dir>/.git/worktrees/

# Disk space
df -h /data/projects
```

### Database (direct psql)

For queries not covered by the diagnostics endpoint:

```bash
psql -h postgres -U teamagent -c "SELECT id, type, status, updated_at FROM chats WHERE status = 'investigating';"
```

## Step 2: Analyse and Reproduce

Before filing, try to understand what happened:

1. **Trace the code path** — read the relevant source files to understand expected vs actual behaviour
2. **Identify the root cause** if possible — is it a race condition, missing check, wrong state transition, data corruption?
3. **Document reproduction steps** — a minimal set of actions that triggers the bug:
   - Starting state (what seed, what existing data)
   - Numbered steps (API calls, messages sent, actions taken)
   - Expected result
   - Actual result (including error messages)

If the bug is intermittent or environment-specific and you can't reproduce it, document what you observed and the conditions.

## Step 3: File the Ticket

Create the issue with all gathered context:

```bash
gh issue create --repo bryan-zxc/team-agent \
  --title "<symptom-focused title>" \
  --body "$(cat <<'BODY'
## Bug

<One-paragraph summary: what's broken, what should happen instead>

## Evidence

### Logs
\`\`\`
<relevant log excerpts — stack traces, error messages, timestamps>
\`\`\`

### Database state
\`\`\`
<relevant query results showing the incorrect state>
\`\`\`

### Additional context
<file system state, chat diagnostics output, anything else relevant>

## Steps to Reproduce

1. <starting state>
2. <action>
3. <action>
4. **Expected:** <what should happen>
5. **Actual:** <what happens instead>

## Root Cause

<your analysis of why this is happening — code path, race condition, missing check, etc.>
<include file paths and line numbers>

## Suggested Fix

<if you have a theory on how to fix it, describe it here>
BODY
)" \
  --label "bug" \
  --assignee "@me"
```

### Add to the project board in Backlog:

```bash
ISSUE_URL=$(gh issue list --repo bryan-zxc/team-agent --limit 1 --json url --jq '.[0].url')
gh project item-add 3 --owner bryan-zxc --url "$ISSUE_URL" --format json

ITEM_ID=$(gh project item-list 3 --owner bryan-zxc --limit 500 --format json \
  --jq ".items[] | select(.content.url == \"$ISSUE_URL\") | .id")

if [ -z "$ITEM_ID" ]; then
  echo "ERROR: Could not find issue on the project board"
  exit 1
fi

gh project item-edit \
  --project-id PVT_kwHOCz6Fr84BOi15 \
  --id "$ITEM_ID" \
  --field-id PVTSSF_lAHOCz6Fr84BOi15zg9N0x0 \
  --single-select-option-id f75ad846
```

## Quality Checklist

Before filing, verify your ticket has:

- A title that describes the symptom, not the cause ("Workload stuck in running after merge failure" not "Missing status update call")
- Actual log excerpts with timestamps, not paraphrases
- Database state showing the incorrect records
- Reproduction steps (or explanation of why not reproducible)
- File paths and line numbers for the relevant code
- Root cause analysis if you've identified one

A good bug ticket saves hours of debugging. A bad one just creates another investigation.
