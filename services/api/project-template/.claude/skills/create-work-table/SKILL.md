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

Run the diagnostic script to sample the file and get DuckDB's type inferences. Use `--output-rows 100` to include sample data rows for the type review page:

```bash
python .claude/skills/create-work-table/scripts/sample_file.py \
  --file-path <path-to-file> \
  --limit 10000 \
  --output-rows 100
```

This outputs JSON with column names, DuckDB-inferred types, sample values for each column, `total_rows`, and `sample_rows` (first 100 rows as arrays).

### 3. Assess types and classify columns

DuckDB's automatic type inference is a good starting point but not always correct. Review each column critically and make two decisions:

**SQL type** — the DuckDB storage type. Trust DuckDB's inference in most cases, but watch for:
- **Date columns** — sometimes wrongly read as integers (e.g. `20210315` → `BIGINT`) or strings (e.g. `04sep26` → `VARCHAR`). Check the sample values and recognise date patterns.

**Stats classification** — how the column should be profiled:
- **categorical** — VARCHAR columns, and integer columns that are identifiers (IDs, codes, categories). These get distinct counts and value distributions.
- **numeric** — FLOAT, DOUBLE, DECIMAL, and integer columns that represent quantities or measurements. These get min/max/avg.
- **date** — DATE and TIMESTAMP columns. These get range and time distribution.

The classification is a judgement call that DuckDB cannot make. A column like `customer_id` is INTEGER but categorical — it's an identifier, not a quantity. Only the AI can make this distinction by looking at the column name and sample values.

Also propose SQL-friendly column names: lowercase, alphanumeric and underscores only. Rename any columns with spaces, special characters, or mixed case.

### 4. Generate interactive type review

Generate an interactive HTML page where the user can review and adjust the type mapping in the browser, then approve it with a single click.

1. **Read the HTML template** from `.claude/skills/create-work-table/assets/type-review-template.html`

2. **Build the review data JSON** and substitute it into the template. The template has a single placeholder `{{REVIEW_DATA}}` inside a `<script type="application/json">` tag. Prepare a JSON object with these keys and use Python `str.replace` to inject it:

   ```python
   import json
   review_data = {
       "table_name": "l10wrk_<tablename>",
       "columns": [{"original": "Customer ID", "sql_name": "customer_id", "recommended": "INTEGER", "classification": "categorical"}, ...],
       "sample_rows": sample_output["sample_rows"],  # from step 2
       "total_rows": sample_output["total_rows"],     # from step 2
       "total_cols": len(columns)
   }
   html = template.replace("{{REVIEW_DATA}}", json.dumps(review_data))
   ```

   **Important:** Do not modify any JavaScript code in the template — only replace the `{{REVIEW_DATA}}` placeholder. The JS reads from the JSON block at runtime.

3. **Write the review file** to `data/reviews/<table_name>.html` (create the `data/reviews/` directory if needed)

4. **Commit** the review file. The link in the next step only works if the file has been committed — the application's file browser only shows committed files. No push is required.

5. **Send a link in chat**: `[Review type mapping for <table_name>](data/reviews/<table_name>.html)`

6. **Wait for the user's response.** The user opens the link in the workbench, sees an interactive table with editable SQL names, type dropdowns, classification dropdowns, and 100 rows of sample data. When they click Approve, the page posts the finalised JSON back into this chat as a message, which arrives as a follow-up to you.

7. **Parse the approved JSON** from the follow-up message. The message contains a JSON code block with the structure:
   ```json
   {"status": "approved", "table_name": "...", "columns": [{"original": "...", "sql_name": "...", "recommended": "...", "classification": "..."}, ...]}
   ```
   Use this approved mapping for all subsequent steps.

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
