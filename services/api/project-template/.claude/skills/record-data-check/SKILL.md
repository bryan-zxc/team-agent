---
name: record-data-check
description: Record a data quality check — create the check script, run it, log results in the data check register, and optionally add to the data validation report. Use when recording a data check result, adding a validation script, or logging a check outcome. Triggers on "record check", "data check", "log check", "add check to register", or any request to formally record a data quality finding.
---

# Record Data Check

Create a data check script, run it, log the result in the register, and optionally escalate to the data validation report for client review.

## Data and database paths

```python
import json
from pathlib import Path

manifest = json.loads(Path(".team-agent/manifest.json").read_text())
project_id = manifest["project_id"]
db_path = f"/data/projects/{project_id}/databases/data.duckdb"
```

Connect to DuckDB:

```python
import duckdb
conn = duckdb.connect(db_path)
```

## Workflow

### 1. Create the check script

Write a SQL script in `data/validation/scripts/`. Naming convention: `chk_<descriptive_name>.sql`.

The script should be a `SELECT` that returns the relevant rows for inspection. Zero rows means pass, any rows means fail.

Requirements:
- Must be idempotent and re-runnable at any time
- SQL is preferred for simplicity
- Name should describe what the check verifies, not what it finds (e.g. `chk_order_id_uniqueness.sql` not `chk_duplicate_orders.sql`)

Example:

```sql
-- Check: order_id uniqueness in l10wrk_orders
-- Expectation: order_id should be unique per row
SELECT order_id, COUNT(*) AS occurrence_count
FROM l10wrk_orders
GROUP BY order_id
HAVING COUNT(*) > 1
ORDER BY occurrence_count DESC;
```

### 2. Run the check

For SQL scripts, execute via DuckDB's Python client:

```python
sql = Path("data/validation/scripts/chk_order_id_uniqueness.sql").read_text()
result = conn.execute(sql).fetchall()
columns = [desc[0] for desc in conn.description]
row_count = len(result)
```

For Python scripts (when the check logic is too complex for pure SQL), run with bash:

```bash
uv run python data/validation/scripts/chk_<name>.py
```

Capture:
- Row count (0 = pass, >0 = fail)
- Sample of the output for context

### 3. Assess outcome

Determine pass or fail and describe the finding concisely. Examples:
- "PASS — all order_id values are unique (0 duplicates)"
- "FAIL — 47 order_id values appear more than once, affecting 112 rows"

### 4. Update the register

Add a row to `data/validation/data-check-register.md`:

| Column | Value |
|--------|-------|
| Check | `chk_<name>` |
| Description | What the check verifies (one sentence) |
| Outcome | Pass/fail + brief detail |
| Script | `[chk_<name>.sql](scripts/chk_<name>.sql)` |
| In DV Report | `no` (initially) |
| Last Ran | Today's date (YYYY-MM-DD) |

### 5. Determine if data validation report is needed

**If the check passed (zero rows):** skip this step entirely — there is nothing to escalate.

**If the check failed (rows returned):** determine whether this is an expected or unexpected finding. The key question is: **is this logically expected given the data we have?**

- **Expected finding — skip DV report.** For example: a join check finds 1,000 transaction types in the transactions table that are not in the reference listing provided to us. But the reference listing was described as a "common types" list, not a complete one — so not seeing every type is expected. This does not need client input.
- **Unexpected finding — escalate to DV report.** The finding is not explainable from what we know, and we need client input to proceed. For example: 47 orders appear to be exact duplicates and we cannot determine whether they are data errors or legitimate repeat transactions.

Present the finding and your assessment to the human. If the human agrees it needs client input, proceed to step 6. If the human agrees it is expected, record it in the register and move on.

### 6. If escalating to DV report

Modify the check script to also materialise the result into a `val_*` table. The `val_*` table must contain actual row-level sample data that the client can investigate — never summary statistics, aggregate counts, or description strings. If the client cannot look at the table and understand what is wrong with each row, the table is useless.

```sql
-- Check: order_id uniqueness in l10wrk_orders
CREATE OR REPLACE TABLE val_dup_orders AS
SELECT order_id, COUNT(*) AS occurrence_count
FROM l10wrk_orders
GROUP BY order_id
HAVING COUNT(*) > 1
ORDER BY occurrence_count DESC;

-- Display results
SELECT * FROM val_dup_orders;
```

The `CREATE OR REPLACE TABLE` line goes first so the table is always up to date when the script is re-run. The `SELECT` at the end displays the result for inspection.

Re-run the modified script to create the `val_*` table.

Then invoke `/append-dv` to add the issue to the data validation report.

Update the register: set "In DV Report" to `yes`.

## Re-running checks

When re-running an existing check (e.g. after receiving new data):
1. Execute the existing script
2. Update the register: change "Outcome" and "Last Ran"
3. If the check was already in the DV report, the `val_*` table will be updated automatically by the `CREATE OR REPLACE TABLE` in the script
