---
name: github-board
description: Manage GitHub project board tickets for the teamagent project. Use whenever creating issues, epics, or stories, transitioning ticket status, closing tickets, or any project board management. Triggers on requests to create tickets, track work, manage the backlog, or update issue status.
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

## Issue Hierarchy

Use two levels:

- **Epic** — high-level feature grouping (label: `epic`)
- **Story** — deliverable slice of functionality within an epic (label: `story`)

Stories are linked to epics as sub-issues via the GitHub GraphQL API.

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

## Rules

- Always assign `@me` — this dynamically resolves to whoever is running the command
- Always add issues to project board 3 after creation
- Always use the `epic` or `story` label as appropriate
- When creating stories that belong to an epic, always link them as sub-issues
