---
name: daily-standup
description: Generate a daily standup report showing what everyone did on a given day. Produces an hour-by-hour, chat-by-chat breakdown written to a markdown file, then synthesises a per-person standup summary. Use this skill whenever the user asks for a standup, daily summary, activity report, "what did everyone do today", or wants to know what happened on a specific day.
---

# Daily Standup

Generate a detailed standup report for a given day. The report captures what every human did — including their direct chat messages and their involvement with AI agents (via tool approvals). Output is written progressively to `docs/standup/YYYY-MM-DD.md`.

## Data and file paths

Read the manifest for project context. If relative paths don't work (you're in a worktree), use absolute paths:

```python
import json
from pathlib import Path

manifest = json.loads(Path(".team-agent/manifest.json").read_text())
project_id = manifest["project_id"]
output_dir = f"/data/projects/{project_id}/repo/docs/standup"
```

The API requires an `X-Internal-Key` header. Both the key and base URL are available as environment variables:

```bash
API=${API_BASE_URL:-http://api:8000}
KEY=${INTERNAL_API_KEY:-team-agent-internal}
```

## Workflow

### 1. Determine the date

Default to today's date. If the user specifies a different date, use that instead. Format as `YYYY-MM-DD`.

### 2. Fetch active chats

```bash
API=${API_BASE_URL:-http://api:8000}
KEY=${INTERNAL_API_KEY:-team-agent-internal}

# Read project_id from manifest
PROJECT_ID=$(python3 -c "import json; print(json.loads(open('.team-agent/manifest.json').read())['project_id'])")

curl -s -H "X-Internal-Key: $KEY" "$API/projects/${PROJECT_ID}/daily-activity?date=YYYY-MM-DD"
```

This returns a lightweight list of chats with activity on that date — chat IDs, types, room names, and message counts. No message bodies.

If no chats have activity, tell the user there was no activity on that date and stop.

### 3. Process each chat

For each chat returned, one at a time:

1. **Tell the user** what you're doing: "Summarising {room_name} ({n}/{total} chats)..."
2. **Run the script:**

```bash
PROJECT_ID=$(python3 -c "import json; print(json.loads(open('.team-agent/manifest.json').read())['project_id'])")
export PROJECT_ID

python3 .claude/skills/daily-standup/scripts/generate_standup.py \
  --chat-id <chat_id> \
  --date <YYYY-MM-DD> \
  --output docs/standup/<YYYY-MM-DD>.md \
  --chat-name "<room_name>" \
  --chat-type <chat_type>
```

The script fetches messages and tool approvals for that chat, groups them into hourly windows, summarises each hour via the AI service, and appends the results to the output markdown file. It prints a confirmation when done.

If the script fails or the output indicates no activity, note it and move on to the next chat.

### 4. Commit the report

After all chats are processed:

```bash
git add docs/standup/<YYYY-MM-DD>.md
git commit -m "Add standup report for <YYYY-MM-DD>"
```

### 5. Present the per-person standup

Read the generated markdown file. For each **human** member, collect all the hourly summaries where they appear across all chats and synthesise a per-person standup:

```
**Alice**
- Worked on the forecast dashboard in General chat (09:00–11:00) — directed Zimomo to fix the timezone bug, approved file edits, reviewed the output
- Reviewed Pucky's workload output (14:00–15:00) — denied one file edit with feedback about the schema

**Bob**
- Discussed data ingestion requirements in General chat (10:00–12:00) — provided CSV file specifications
```

Include what the AI agent did as part of the human's progress. If there is no recorded activity for someone explain that there are no recorded activities for them, don't skip anyone.

### 6. Handle follow-up questions

If the user asks for more detail about a specific person, time window, or chat, refer back to the hourly breakdown in the markdown file. The file contains the full detailed summaries — read the relevant section and present it.
