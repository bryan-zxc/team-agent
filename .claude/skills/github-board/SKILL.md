---
name: github-board
description: Manage GitHub project board tickets for the teamagent project. Use whenever creating issues — epics, stories, or bugs — transitioning ticket status, closing tickets, or any project board management. Triggers on requests to create tickets, track work, manage the backlog, or update issue status.
---

# GitHub Board Management

## Project Board Details

- **Project number:** 3
- **Project node ID:** PVT_kwHOCz6Fr84BOi15
- **Repo:** bryan-zxc/team-agent
- **Status field ID:** PVTSSF_lAHOCz6Fr84BOi15zg9N0x0

### Status Options

| Status | Option ID |
|---|---|
| Backlog | f75ad846 |
| Ready | 61e4505c |
| In progress | 47fc9ee4 |
| In review | df73e18b |
| Done | 98236657 |

## Issue Types

- **Epic** — high-level feature grouping (label: `epic`)
- **Story** — deliverable slice of functionality within an epic (label: `story`)
- **Bug** — something that used to work but is now broken (label: `bug`)

Stories are linked to epics as sub-issues via the GitHub GraphQL API. Bugs are standalone — they don't belong to an epic.

## Creating an Epic

```bash
gh issue create --repo bryan-zxc/team-agent \
  --title "Epic title" \
  --body "Description" \
  --label "epic" \
  --assignee "@me"
```

Then add to the project board:

```bash
gh project item-add 3 --owner @me --url <issue-url> --format json
```

## Creating a Bug

```bash
gh issue create --repo bryan-zxc/team-agent \
  --title "Bug title" \
  --body "Description" \
  --label "bug" \
  --assignee "@me"
```

Then add to the project board:

```bash
gh project item-add 3 --owner @me --url <issue-url> --format json
```

## Creating a Story Under an Epic

Create the story issue:

```bash
gh issue create --repo bryan-zxc/team-agent \
  --title "Story title" \
  --body "Description" \
  --label "story" \
  --assignee "@me"
```

Add to the project board:

```bash
gh project item-add 3 --owner @me --url <issue-url> --format json
```

Link as sub-issue to the epic using node IDs:

```bash
EPIC_NODE_ID=$(gh api repos/bryan-zxc/team-agent/issues/<epic-number> --jq '.node_id')
STORY_NODE_ID=$(gh api repos/bryan-zxc/team-agent/issues/<story-number> --jq '.node_id')

gh api graphql -f query="
mutation {
  addSubIssue(input: {issueId: \"$EPIC_NODE_ID\", subIssueId: \"$STORY_NODE_ID\"}) {
    issue { id title }
    subIssue { id title }
  }
}"
```

## Transitioning Status

Get the item ID from the `gh project item-add` output (`id` field), then:

```bash
gh project item-edit \
  --project-id PVT_kwHOCz6Fr84BOi15 \
  --id <item-id> \
  --field-id PVTSSF_lAHOCz6Fr84BOi15zg9N0x0 \
  --single-select-option-id <status-option-id>
```

Use the status option IDs from the table above.

## Closing a Ticket

```bash
gh issue close <issue-number> --repo bryan-zxc/team-agent
```

## Ticket Workflow

- When picking up a ticket: transition status to **In progress**
- When done with a ticket: transition status to **Done** and close the issue
- If a ticket needs to change, edit the description to the correct version — describe clearly what is eventually done, not what changed from before. Never add comments to tickets.

## Rules

- Always assign `@me` — this dynamically resolves to whoever is running the command
- Always add issues to project board 3 after creation
- Always use the `epic`, `story`, or `bug` label as appropriate
- When creating stories that belong to an epic, always link them as sub-issues
- **Naming**: Name tickets from the user's perspective (developers are users too). Describe the benefit, not the technical implementation. E.g. "Reproducible database setup across environments" not "Set up Alembic".
- **Context-rich descriptions**: Every ticket must contain enough context for a brand new Claude Code session to pick it up and deliver — current state, what to build, file paths, data model references, and verification steps. A reader should never need to chase down external context to understand or implement the ticket.
