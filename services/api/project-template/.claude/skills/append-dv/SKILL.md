---
name: append-dv
description: Append a data validation issue to the validation report for client review. Use when a data check has identified something that requires client input and the val_ table already exists in DuckDB. Triggers on "add to validation report", "append dv", "raise validation issue", "add DV issue", or any request to add an issue to the data validation report.
---

# Append Data Validation Issue

Add a single issue to `data/validation/report_data.json` for client review. The `val_*` table must already exist in DuckDB before calling this skill.

## Workflow

### 1. Read current report

Read `data/validation/report_data.json`. If it doesn't exist or is empty, initialise it:

```json
{
  "project_name": "",
  "report_title": "Data Validation Report",
  "generated_at": null,
  "issues": []
}
```

### 2. Check for duplicates

Search existing issues by `sample_table` name and question content:

- **Decided items are immutable** — never modify them under any circumstances. If an existing decided issue fully covers this finding, skip — do not raise a duplicate. If it partially covers it, narrow the new issue to only the uncovered part, including narrowing the `val_*` table to exclude already-decided rows.
- **Open items can be amended** — if an existing open issue covers the same ground, propose the amendment to the human. Wait for explicit confirmation before modifying. If the human declines, raise a separate narrowed issue or skip entirely.

### 3. Auto-generate ID

Find the highest existing `DQ-NNN` number in the issues array, increment by 1. First issue is `DQ-001`.

### 4. Draft the issue

Prepare the issue with these fields:

- `id`: auto-generated (e.g. `DQ-003`)
- `status`: `"open"`
- `priority`: recommend one of `"high"`, `"medium"`, `"low"` — but present to the human for confirmation. The human decides.
- `question`: **Must be phrased as a client-facing ask tied to the analysis need.** Use the format: "We need [confirmation/clarification/decision] on [what] because [how the analysis depends on it]." If there is no ask — if we don't need anything from the client — it does not belong in the data validation report.
- `proposed_solution`: what we recommend doing and why
- `sample_table`: the `val_*` table name (must already exist in DuckDB)
- `final_decision`: `""` (empty — client fills this in via the report UI)
- `comments`: `""` (empty — client fills this in via the report UI)

**Bad example:** "We found 47 duplicate orders based on order_id."
**Good example:** "We need your confirmation on whether these 47 orders with identical order_id values are true duplicates that should be removed, or legitimate repeat transactions that should be aggregated — our revenue analysis requires each order counted exactly once to get accurate totals."

### 5. Present to human

Show the complete drafted issue to the human for approval before writing. Include the question, proposed solution, priority recommendation, and sample table name. The human may adjust any field.

### 6. Write

- Set `generated_at` to the current ISO 8601 timestamp if not already set
- Set `project_name` and `report_title` if currently empty (derive from the project context)
- Append the approved issue to the `issues` array
- Write the updated JSON back to `data/validation/report_data.json`
