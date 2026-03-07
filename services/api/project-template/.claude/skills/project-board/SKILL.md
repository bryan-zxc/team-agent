---
name: project-board
description: Manage the project board. Use whenever creating tickets (epics or tasks), transitioning status, or managing the backlog. Triggers on requests to create tickets, track work, manage the backlog, or update ticket status.
---

# Project Board Management

## Setup — Read Board Config

Before any board operation, read the board configuration from the manifest:

```bash
BOARD_JSON=$(cat .team-agent/manifest.json | jq -r '.board')

PROJECT_NUMBER=$(echo "$BOARD_JSON" | jq -r '.project_number')
PROJECT_NODE_ID=$(echo "$BOARD_JSON" | jq -r '.project_node_id')
STATUS_FIELD_ID=$(echo "$BOARD_JSON" | jq -r '.status_field_id')
START_DATE_FIELD_ID=$(echo "$BOARD_JSON" | jq -r '.start_date_field_id')
TARGET_DATE_FIELD_ID=$(echo "$BOARD_JSON" | jq -r '.target_date_field_id')

# Status option IDs
BACKLOG_ID=$(echo "$BOARD_JSON" | jq -r '.status_options.Backlog')
READY_ID=$(echo "$BOARD_JSON" | jq -r '.status_options.Ready')
IN_PROGRESS_ID=$(echo "$BOARD_JSON" | jq -r '.status_options["In progress"]')
IN_REVIEW_ID=$(echo "$BOARD_JSON" | jq -r '.status_options["In review"]')
DONE_ID=$(echo "$BOARD_JSON" | jq -r '.status_options.Done')
```

Get the repo from git remote:

```bash
REPO=$(git remote get-url origin | sed 's|.*github.com[:/]||;s|\.git$||')
```

### Status Options

| Status | Variable |
|---|---|
| Backlog | `$BACKLOG_ID` |
| Ready | `$READY_ID` |
| In progress | `$IN_PROGRESS_ID` |
| In review | `$IN_REVIEW_ID` |
| Done | `$DONE_ID` |

## Issue Types

- **Epic** — high-level feature grouping (label: `epic`). Gets start date + target date.
- **Task** — deliverable work item within an epic (label: `task`). Optionally gets target date only.

Tasks are linked to epics as sub-issues via the GitHub GraphQL API.

## Adding to Board

After creating any issue, add it to the board **and immediately set its status to Backlog**. Items added via CLI have no status by default — without this step they won't appear in any board column.

```bash
ITEM_ID=$(gh project item-add $PROJECT_NUMBER --owner @me --url <issue-url> --format json --jq '.id')

gh project item-edit \
  --project-id $PROJECT_NODE_ID \
  --id "$ITEM_ID" \
  --field-id $STATUS_FIELD_ID \
  --single-select-option-id $BACKLOG_ID
```

## Creating an Epic

```bash
gh issue create --repo $REPO \
  --title "Epic title" \
  --body "Description" \
  --label "epic" \
  --assignee "@me"
```

Then add to the project board (see [Adding to Board](#adding-to-board)).

Set start date and target date on the board item:

```bash
gh project item-edit \
  --project-id $PROJECT_NODE_ID \
  --id "$ITEM_ID" \
  --field-id $START_DATE_FIELD_ID \
  --date "YYYY-MM-DD"

gh project item-edit \
  --project-id $PROJECT_NODE_ID \
  --id "$ITEM_ID" \
  --field-id $TARGET_DATE_FIELD_ID \
  --date "YYYY-MM-DD"
```

## Creating a Task Under an Epic

Create the task issue:

```bash
gh issue create --repo $REPO \
  --title "Task title" \
  --body "Description" \
  --label "task" \
  --assignee "@me"
```

Add to the project board (see [Adding to Board](#adding-to-board)).

Optionally set target date:

```bash
gh project item-edit \
  --project-id $PROJECT_NODE_ID \
  --id "$ITEM_ID" \
  --field-id $TARGET_DATE_FIELD_ID \
  --date "YYYY-MM-DD"
```

Link as sub-issue to the epic using node IDs:

```bash
EPIC_NODE_ID=$(gh api repos/$REPO/issues/<epic-number> --jq '.node_id')
TASK_NODE_ID=$(gh api repos/$REPO/issues/<task-number> --jq '.node_id')

gh api graphql -f query="
mutation {
  addSubIssue(input: {issueId: \"$EPIC_NODE_ID\", subIssueId: \"$TASK_NODE_ID\"}) {
    issue { id title }
    subIssue { id title }
  }
}"
```

## Transitioning Status

Use the item ID captured from `gh project item-add` (see [Adding to Board](#adding-to-board)), or look it up (see [Looking Up Item IDs](#looking-up-item-ids)). Then:

```bash
gh project item-edit \
  --project-id $PROJECT_NODE_ID \
  --id <item-id> \
  --field-id $STATUS_FIELD_ID \
  --single-select-option-id <status-option-id>
```

Use the status option variables from the table above.

## Looking Up Item IDs

**Always use `--limit 500`** when querying the project board — the default limit is 30, which silently omits items beyond that. **Always guard against empty results** before passing the ID to `gh project item-edit`.

```bash
ITEM_ID=$(gh project item-list $PROJECT_NUMBER --owner @me --limit 500 --format json --jq ".items[] | select(.content.number == <issue-number>) | .id")

if [ -z "$ITEM_ID" ]; then
  echo "ERROR: Could not find issue <issue-number> on the project board"
  exit 1
fi
```

## Completing a Ticket

To complete a ticket, transition its board status to **Done**. Look up the item ID first, guard against empty, then set the status:

```bash
ITEM_ID=$(gh project item-list $PROJECT_NUMBER --owner @me --limit 500 --format json --jq ".items[] | select(.content.number == <issue-number>) | .id")

if [ -z "$ITEM_ID" ]; then
  echo "ERROR: Could not find issue <issue-number> on the project board"
  exit 1
fi

gh project item-edit \
  --project-id $PROJECT_NODE_ID \
  --id "$ITEM_ID" \
  --field-id $STATUS_FIELD_ID \
  --single-select-option-id $DONE_ID
```

**Never use `gh issue close`** — issue state (open/closed) is not the same as board status. Always use board status transitions.

## Ticket Workflow

- When picking up a ticket: transition board status to **In progress**
- When done with a ticket: transition board status to **Done**
- If a ticket needs to change, edit the description to the correct version — describe clearly what is eventually done, not what changed from before. Never add comments to tickets.

## Rules

- **Never use `gh issue close` or `gh issue reopen`** — manage completion exclusively through board status transitions. Issue state (open/closed) and board status (Backlog/Ready/In progress/In review/Done) are separate concepts; we only use board status.
- Always assign `@me` — this dynamically resolves to whoever is running the command
- Always add issues to the project board after creation
- Always use the `epic` or `task` label as appropriate
- When creating tasks that belong to an epic, always link them as sub-issues
- **Naming**: Name tickets from the user's perspective. Describe the benefit, not the technical implementation. E.g. "Reproducible database setup across environments" not "Set up Alembic".
- **Context-rich descriptions**: Every ticket must contain enough context for a brand new Claude Code session to pick it up and deliver — current state, what to build, file paths, data model references, and verification steps. A reader should never need to chase down external context to understand or implement the ticket.
