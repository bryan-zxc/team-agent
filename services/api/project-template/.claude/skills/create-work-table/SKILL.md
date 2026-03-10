---
name: create-work-table
description: Ingest a source file (CSV, Excel, Parquet) into the project's DuckDB database as a working-layer table (l10wrk_). Use this skill whenever the user wants to load, import, or ingest a file into DuckDB, create a working table, or get data from a file into the database. Triggers on "load this file", "import csv", "ingest data", "create work table", "create working table", "l10wrk", or any request to turn a file into a DuckDB table.
---

# Create Work Table

Ingest a source file into DuckDB as an `l10wrk_` working-layer table with properly typed columns, then generate table documentation with column statistics.

Read `references/layers.md` (via the `create-table` skill) for the full layer naming convention.

## Data and database paths

Source data files live in `data/raw/` and the database lives outside the repo. If the relative path doesn't work, you are in a git worktree — use absolute paths derived from the manifest instead:

```python
import json
from pathlib import Path

manifest = json.loads(Path(".team-agent/manifest.json").read_text())
project_id = manifest["project_id"]
data_dir = f"/data/projects/{project_id}/repo/data/raw"
db_path = f"/data/projects/{project_id}/databases/data.duckdb"
```

## Workflow

### 1. Identify the file and table name

Confirm with the user:
- **Source file** — typically in `data/raw/`
- **Table name** — must follow the pattern `l10wrk_<descriptive_name>` (lowercase, underscores, describes the content not the file)

If the user provides a file but no table name, suggest one based on the file content.

### 2. Sample and infer types

Run the diagnostic script to sample the file and get DuckDB's type inferences:

```bash
python .claude/skills/create-work-table/scripts/sample_file.py \
  --file-path <path-to-file> \
  --limit 10000
```

This outputs JSON with column names, DuckDB-inferred types, and sample values for each column.

### 3. Assess types and classify columns

DuckDB's automatic type inference is a good starting point but not always correct. Review each column critically and make two decisions:

**SQL type** — the DuckDB storage type:
- **ID columns** (e.g. `customer_id`, `order_id`, `sku`) — often inferred as `BIGINT` but should be `INTEGER` for faster querying. IDs are for joining and filtering, not arithmetic.
- **Date columns** — sometimes wrongly read as integers (e.g. `20210315` → `BIGINT`) or strings (e.g. `04sep26` → `VARCHAR`). Check the sample values and recognise date patterns.
- **Boolean columns** — may be inferred as `VARCHAR` if values are `Y/N`, `yes/no`, `true/false`, `1/0`.

**Stats classification** — how the column should be profiled:
- **categorical** — VARCHAR columns, and integer columns that are identifiers (IDs, codes, categories). These get distinct counts and value distributions.
- **numeric** — FLOAT, DOUBLE, DECIMAL, and integer columns that represent quantities or measurements. These get min/max/avg.
- **date** — DATE and TIMESTAMP columns. These get range and time distribution.

The classification is a judgement call that DuckDB cannot make. A column like `customer_id` is INTEGER but categorical — it's an identifier, not a quantity. Only the AI can make this distinction by looking at the column name and sample values.

Also propose SQL-friendly column names: lowercase, alphanumeric and underscores only. Rename any columns with spaces, special characters, or mixed case.

### 4. Present type mapping for confirmation

Show the proposed mapping as a table:

```
| # | Original Column | SQL Name     | Inferred | Recommended | Classification | Notes              |
|---|-----------------|--------------|----------|-------------|----------------|--------------------|
| 1 | Customer ID     | customer_id  | BIGINT   | INTEGER     | categorical    | ID column          |
| 2 | Revenue         | revenue      | DOUBLE   | DOUBLE      | numeric        |                    |
| 3 | Receipt Date    | receipt_date | BIGINT   | DATE        | date           | Read as integer    |
| 4 | Region          | region       | VARCHAR  | VARCHAR     | categorical    |                    |
```

End with: "Reply with any changes or approve to proceed."

Wait for the user to respond. They may say "approve", suggest changes ("change 2 to VARCHAR"), or ask questions. Apply any requested changes and re-present if needed.

### 5. Create the ingestion script

After the user approves, write a Python ingestion script tailored to this specific file and the confirmed type mappings. Read `references/ingestion-guide.md` for the approach, patterns, and code examples — adapt them to the situation rather than copying verbatim.

The script must:
- Use `CREATE OR REPLACE TABLE` so it is idempotent
- Apply the confirmed column renames and type conversions
- Connect to DuckDB using the project's manifest for the database path
- Print a summary (row count, column count)

Save the script to `analysis/l10wrk_<tablename>.py`. One script per table, named identically to the table — no exceptions.

Execute the script to create the table.

### 6. Add to pipeline

Add the script as a step in `analysis/pipeline.yml`, creating the file if it doesn't exist:

```yaml
steps:
  - name: Ingest sales
    script: l10wrk_sales.py
```

### 7. Generate column statistics

After the table is created, run the column stats script. Pass the approved classification from step 4 so the script knows which stats to compute for each column:

```bash
python .claude/skills/create-work-table/scripts/column_stats.py \
  --db-path <path-to-duckdb> \
  --table-name l10wrk_<tablename> \
  --column-types '{"customer_id": "categorical", "revenue": "numeric", "receipt_date": "date", "region": "categorical"}'
```

The script outputs JSON with per-column statistics tailored to each classification.

### 8. Write table documentation

Read `references/doc-template.md` for the documentation format. Using the column stats JSON, generate a markdown file at `docs/tables/l10wrk_<tablename>.md`.

Then update `docs/tables/tables.md` by adding a row to the index table:

```markdown
| l10wrk_<tablename> | Brief description | [View](l10wrk_<tablename>.md) |
```

### 9. Confirm completion

Summarise what was created:
- Table name and row count
- Link to the documentation file
- Link to the ingestion script
- Any notable findings from the column stats (e.g. high null counts, unexpected values)
