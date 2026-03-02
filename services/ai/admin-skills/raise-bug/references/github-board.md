# GitHub Board Reference

File bug tickets on the `bryan-zxc/team-agent` repo and add them to project board 3 in Backlog status.

## Create the issue

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

### Chat/workload diagnostics
<output from /diagnostics/chats/{id} — chat state, workload state, recent messages>

### Additional context
<file system state at /data/projects/, anything else relevant>

## Steps to Reproduce

1. <starting state>
2. <action>
3. <action>
4. **Expected:** <what should happen>
5. **Actual:** <what happens instead>

## Root Cause

<your analysis based on the evidence — what state is wrong, what operation failed, what sequence of events led here>

## Suggested Fix

<if you have a theory on how to fix it, describe it here>
BODY
)" \
  --label "bug" \
  --assignee "@me"
```

## Add to the project board in Backlog

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

## Ticket quality

A good title describes the **symptom** from the user's perspective, not the technical cause:
- "Chat scrolls to oldest message instead of newest when entering a room"
- "Workload stuck in running after merge failure"

Not:
- "Missing scrollIntoView call in ChatView"
- "Status update not called in stop_hook"

The body should include actual evidence — log excerpts with timestamps, diagnostics output, reproduction steps. A developer picking up this ticket should be able to understand and fix the issue without starting a fresh investigation.
