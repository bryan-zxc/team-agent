---
name: do-timesheet
description: Generate and submit timesheets from tracked active time. Use when a user asks to create timesheets, log hours, submit time, review billable hours, or convert tracked time into timesheet entries. Triggers on "do my timesheet", "timesheet", "log hours", "submit time", "how many hours", "what should my timesheet be", "billable hours", or any request about converting tracked activity into time entries.
---

# Do Timesheet

Generate timesheet entries from a human member's tracked active time. The system records one heartbeat per minute of user activity — this skill reads those heartbeats, applies a configurable markup, rounds to the nearest 0.5h, and saves approved entries.

## Setup

Read the project manifest to get the project ID:

```bash
PROJECT_ID=$(cat .team-agent/manifest.json | python3 -c "import sys,json; print(json.load(sys.stdin)['project_id'])")
```

### API authentication

The API requires an `X-Internal-Key` header for service-to-service calls. The key is available as the `INTERNAL_API_KEY` environment variable (injected into your environment by the workload runner). The API base URL is in `API_BASE_URL` (defaults to `http://api:8000`).

```bash
API=${API_BASE_URL:-http://api:8000}
curl -s -H "X-Internal-Key: $INTERNAL_API_KEY" "$API/..."
```

## Workflow

### 1. Identify the member and date range

Determine who is asking and for what period. Default to the current work week (Monday to Friday) if the user doesn't specify.

Look up the member by fetching all project members and matching on display name:

```bash
curl -s -H "X-Internal-Key: $INTERNAL_API_KEY" \
  "$API/projects/$PROJECT_ID/members"
```

Find the member whose `display_name` matches the requesting user. Extract their `id` as `MEMBER_ID`.

If the member's `type` is not `"human"`, explain that timesheets are only for human members.

### 2. Fetch daily heartbeat data

```bash
curl -s -H "X-Internal-Key: $INTERNAL_API_KEY" \
  "$API/projects/$PROJECT_ID/members/$MEMBER_ID/heartbeat-daily?start=YYYY-MM-DD&end=YYYY-MM-DD"
```

The `start` and `end` dates are **inclusive** — both boundary dates are included in the results. For example, `start=2026-03-10&end=2026-03-14` returns data for Mon 10th through Fri 14th.

Returns: `[{"date": "2026-03-10", "minutes": 232}, ...]`

Only days with at least one heartbeat appear in the response — days with zero activity are omitted entirely.

If the response is empty, the member had no tracked activity in that period — let them know and ask if they want to try a different date range.

### 3. Fetch member settings

```bash
curl -s -H "X-Internal-Key: $INTERNAL_API_KEY" \
  "$API/projects/$PROJECT_ID/members/$MEMBER_ID/settings"
```

Returns: `{"settings": {"timesheet_markup": 30, ...}, "defaults": {"timesheet_markup": 30.0, ...}}`

Use the `timesheet_markup` value from `settings`. If not set, fall back to `defaults.timesheet_markup` (30%).

### 4. Check for existing timesheets

```bash
curl -s -H "X-Internal-Key: $INTERNAL_API_KEY" \
  "$API/projects/$PROJECT_ID/members/$MEMBER_ID/timesheets?start=YYYY-MM-DD&end=YYYY-MM-DD"
```

Returns: `[{"date": "2026-03-10", "hours": 7.5}, ...]`

If entries already exist for any dates in the range, flag them in the proposal so the user knows they'll be overwritten.

### 5. Calculate timesheet hours

For each day with tracked activity:

1. **Convert to hours:** `raw_hours = minutes / 60`
2. **Apply markup:** `marked_up = raw_hours * (1 + timesheet_markup / 100)`
3. **Round up to nearest 0.5h:** `hours = ceil(marked_up * 2) / 2`
4. **Minimum 0.5h:** Any day with activity (minutes > 0) gets at least 0.5h

Days with zero tracked minutes are excluded entirely — do not create entries for days with no activity.

### 6. Present the proposal

Show a markdown table with all the detail:

```
Using **30% markup** (from member settings).

| Date       | Tracked | Raw Hours | + Markup | Timesheet |
|------------|---------|-----------|----------|-----------|
| Mon 10 Mar | 232m    | 3.87h     | 5.03h    | 5.5h      |
| Tue 11 Mar | 185m    | 3.08h     | 4.01h    | 4.5h      |
| Wed 12 Mar | 0m      | —         | —        | —         |
| Thu 13 Mar | 412m    | 6.87h     | 8.93h    | 9.0h      |
| Fri 14 Mar | 28m     | 0.47h     | 0.61h    | 1.0h      |
| **Total**  | **857m**| **14.28h**| **18.57h**| **20.0h** |
```

If any dates have existing entries, add a note: "Note: entries for Mon 10 Mar (currently 5.0h) and Thu 13 Mar (currently 8.5h) will be updated."

Then ask: "Shall I submit this timesheet? You can also ask me to adjust individual entries before submitting."

### 7. Handle adjustments

If the user wants to change specific entries (e.g., "make Monday 6h" or "remove Friday"), apply the changes and show the updated table. Repeat until the user is happy.

If the user wants to change the markup percentage, update it via the settings endpoint:

```bash
curl -s -X PUT -H "X-Internal-Key: $INTERNAL_API_KEY" \
  -H "Content-Type: application/json" \
  "$API/projects/$PROJECT_ID/members/$MEMBER_ID/settings" \
  -d '{"settings": {"timesheet_markup": 50}}'
```

Then recalculate and show the updated proposal.

### 8. Submit on approval

When the user approves, save entries via bulk upsert:

```bash
curl -s -X POST -H "X-Internal-Key: $INTERNAL_API_KEY" \
  -H "Content-Type: application/json" \
  "$API/projects/$PROJECT_ID/members/$MEMBER_ID/timesheets" \
  -d '{"entries": [{"date": "2026-03-10", "hours": 5.5}, {"date": "2026-03-11", "hours": 4.5}, ...]}'
```

The upsert behaviour means re-running for the same dates updates rather than duplicates.

### 9. Confirm

Summarise what was saved: number of entries, total hours, date range. Remind the user they can re-run the skill anytime to update entries if tracked time changes.
