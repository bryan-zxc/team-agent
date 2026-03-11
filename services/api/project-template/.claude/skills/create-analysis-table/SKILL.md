---
name: create-analysis-table
description: Create a derived (l20drv_) or export (l30exp_) table in the project's DuckDB database by writing SQL that transforms existing tables. Use this skill whenever the user wants to create a derived table, build an export table, aggregate data, join tables, or create any table from existing DuckDB tables. Triggers on "create derived table", "create export table", "l20drv", "l30exp", "aggregate", "join tables", "transform data", or any request to build a new table from existing ones.
---

# Create Analysis Table

Create a derived or export table by writing SQL (or Python if needed) that transforms existing DuckDB tables, then generate table documentation.

## Workflow

### 1. Determine layer and table name

Ask the user if unclear, but most requests fall into obvious categories:

- **Derived (l20drv_)** — transformations, joins, aggregations, business logic. Source is working tables or other derived tables.
- **Export (l30exp_)** — final tables shaped for reporting or external consumption. Minimal transformation from derived tables — primarily filtering, renaming, and formatting.

Table name must follow the pattern `l20drv_<descriptive_name>` or `l30exp_<descriptive_name>` (lowercase, underscores, describes the content).

### 2. Understand available tables

Read the table documentation in `docs/tables/` to understand what tables exist, their columns, types, and key notes. Start with the index at `docs/tables/tables.md`.

### 3. Write the query

Write SQL (recommended) or Python to create the table. The script can have as many intermediate steps as needed — CTEs, temp tables, multiple inserts — but must produce exactly one final table.

The final table must use `CREATE OR REPLACE TABLE` so the script is idempotent.

Save to `analysis/<table_name>.sql` (or `.py`). One script per table, named identically to the table — no exceptions.

Example SQL:

```sql
CREATE OR REPLACE TABLE l20drv_sales_by_region AS
SELECT
    region,
    DATE_TRUNC('quarter', order_date) AS quarter,
    COUNT(*) AS transaction_count,
    SUM(revenue) AS total_revenue,
    AVG(revenue) AS avg_revenue
FROM l10wrk_sales
WHERE order_date IS NOT NULL
GROUP BY region, quarter
ORDER BY region, quarter;
```

Execute the script to create the table.

### 4. Confirm primary key

Every analysis table must have a primary key — a column or combination of columns that uniquely identifies each row. The primary key serves two purposes: it catches unintended duplicates in the data, and it guides downstream joins. When another table needs to join to this one, the primary key tells the reader exactly which columns to join on to avoid unintentional row duplication in the result.

This is why an auto-generated surrogate key is not sufficient — it is guaranteed unique by construction so it catches nothing, and it provides no guidance on how to correctly join to this table.

Confirm the primary key with the user, then verify it after the table is built:

```sql
SELECT region, quarter, COUNT(*) AS cnt
FROM l20drv_sales_by_region
GROUP BY region, quarter
HAVING cnt > 1;
```

Empty result means the key is valid. If duplicates exist, investigate and fix the query before proceeding.

If the table has both a primary key and a separate unique constraint, record both in `docs/tables/`.

### 5. Add to pipeline

Add the script as a step in `analysis/pipeline.yml`, creating the file if it doesn't exist. Place it after any tables it depends on:

```yaml
steps:
  - name: Ingest sales
    script: l10wrk_sales.py
  - name: Sales by region
    script: l20drv_sales_by_region.sql
```

### 6. Write table documentation

Read `references/doc-template.md` for the documentation format. Generate a markdown file at `docs/tables/<table_name>.md`.

Then update `docs/tables/tables.md` by adding a row to the index table:

```markdown
| l20drv_sales_by_region | Regional sales aggregated by quarter | [View](l20drv_sales_by_region.md) |
```

### 7. Confirm completion

Summarise what was created:
- Table name and row count
- Primary key
- Link to the documentation file
- Link to the SQL script
