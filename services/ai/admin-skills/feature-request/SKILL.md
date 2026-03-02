---
name: feature-request
description: Create a feature request ticket on the GitHub project board. Use this skill whenever you identify a missing capability, a workflow improvement, or something the system should do but doesn't yet. Triggers on any mention of feature request, enhancement, improvement idea, or "this should be a ticket".
---

# Feature Request

When you notice a gap in the system — a missing capability, a workflow that could be smoother, or something that would have prevented the issue you're investigating — capture it as a feature request ticket.

## Steps

1. **Draft the ticket** with a clear user-facing title and a description that contains enough context for a fresh session to pick it up. Include:
   - What the feature enables (the benefit, not the implementation)
   - Current behaviour and why it's insufficient
   - Relevant file paths, data models, or architectural context
   - Acceptance criteria if obvious

2. **Create the issue:**
   ```bash
   gh issue create --repo bryan-zxc/team-agent \
     --title "<title>" \
     --body "<description>" \
     --label "story" \
     --assignee "@me"
   ```

3. **Add to the project board:**
   ```bash
   ISSUE_URL=$(gh issue list --repo bryan-zxc/team-agent --limit 1 --json url --jq '.[0].url')
   gh project item-add 3 --owner bryan-zxc --url "$ISSUE_URL" --format json
   ```

4. **Set status to Backlog:**
   ```bash
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

## Writing Good Tickets

- **Title**: Name from the user's perspective — describe the benefit, not the implementation. "Reproducible database setup across environments" not "Set up Alembic".
- **Label**: Use `story` for feature work, `epic` only for high-level groupings.
- **Description**: A reader should never need to chase down external context. Include current state, what to build, file paths, and verification steps.
- **No comments**: If the ticket needs updating, edit the description directly.
