---
name: create-forecast
description: Create or update the resource forecast for the resourcing dashboard. Guides the user through setting up team members, their days per week, Australian state (for public holidays), and expected leave, then generates forecast.json with daily granularity. Use this skill whenever the user wants to create a forecast, plan resourcing, set up the forecast, update the forecast, or mentions forecast.json.
---

# Create Forecast

Generate `docs/governance/forecast.json` — the data source for the resourcing dashboard. The forecast is daily-granular: each member has a value for every weekday in the period. The dashboard aggregates to weekly for the overview and uses exact daily values for the drill-down.

## Data and file paths

The forecast file lives at `docs/governance/forecast.json` in the project repo. If relative paths don't work (you're in a worktree), use absolute paths:

```python
import json
from pathlib import Path

manifest = json.loads(Path(".team-agent/manifest.json").read_text())
project_id = manifest["project_id"]
output_path = f"/data/projects/{project_id}/repo/docs/governance/forecast.json"
```

## Workflow

### 1. Fetch and present team members

Read the manifest, then fetch project members. The API requires an `X-Internal-Key` header. The key is available as the `INTERNAL_API_KEY` environment variable and the API base URL is in `API_BASE_URL` (defaults to `http://api:8000`).

```bash
API=${API_BASE_URL:-http://api:8000}
KEY=${INTERNAL_API_KEY:-team-agent-internal}
curl -s -H "X-Internal-Key: $KEY" "$API/projects/${PROJECT_ID}/members"
```

Present the members grouped by type:

```
**People:**
- Alice (human)
- Bob (human)

**Agents:**
- Zimomo (coordinator)
- Molly (ai)
- Pucky (ai)
```

### 2. Ask about additional people

Some team members may not have been added to the project yet. Ask: *"Are there any other people working on this project who aren't listed above?"*

If yes, collect their names.

### 3. Ask for forecast period

Ask: *"What start date and how many weeks should the forecast cover?"*

The start date should be a Monday. If the user gives a non-Monday, snap to the preceding Monday.

### 4. Collect human details

For each human member, ask their **Australian state** and **how many days per week** they work on this project:

*"For each person, I need their Australian state (for public holidays) and how many days per week they work on this project:"*

Present as a table for confirmation:

| Person | State | Days/week |
|--------|-------|-----------|
| Alice  | NSW   | 5         |
| Bob    | VIC   | 2.5       |

Days are assigned from Monday forward: 3 days = Mon/Tue/Wed. 2.5 days = Mon/Tue full + Wed half day. Each full day = 7.5 hours.

### 5. Ask about expected leave

Ask: *"Does anyone have planned leave during this period? Provide date ranges (e.g. Alice: 14 Apr – 18 Apr)."*

### 6. Generate the forecast

Build the input JSON and run the script:

```bash
uv run python .claude/skills/create-forecast/scripts/generate_forecast.py \
  --input '{
    "start_date": "2026-03-09",
    "weeks": 13,
    "humans": [
      {"name": "Alice", "state": "NSW", "days_per_week": 5, "leave": [["2026-04-14", "2026-04-18"]]},
      {"name": "Bob", "state": "VIC", "days_per_week": 2.5, "leave": []}
    ],
    "agents": ["Zimomo", "Molly", "Pucky"]
  }'
```

The script:
- Assigns working days from Monday forward based on `days_per_week`
- Sets 0 on public holidays (per state) and leave days
- Sets agents to $100/day on any day where at least one human is working
- Writes `docs/governance/forecast.json`
- Prints a weekly summary table with public holidays and leave

### 7. Commit and provide review link

Commit the forecast file:

```bash
git add docs/governance/forecast.json
git commit -m "Update resource forecast"
```

Then send a link so the user can see the forecast in the resourcing dashboard:

```
[View resourcing forecast](docs/governance/resourcing.html)
```

The user can review the weekly and daily breakdown in the dashboard. If adjustments are needed, update the inputs and re-run the script.

## Key assumptions

- **Full day = 7.5 hours**, days assigned from Monday forward
- **Agent daily budget = $100** — agents work on any day where at least one human is working
- **Public holidays** are determined by each person's Australian state using the `holidays` library
- **Weekends** (Saturday/Sunday) are always excluded
- **Leave** is specified as inclusive date ranges
