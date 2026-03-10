# Ingestion Guide

Each ingestion script is bespoke — written for a specific file and set of confirmed type mappings. Use this guide for patterns and approach, adapting to the situation rather than copying verbatim.

Every script must be **idempotent**: starts with `CREATE OR REPLACE TABLE`, uses the same source file(s), and always produces the exact same table when re-run.

## Database and data paths

All scripts connect to the project's DuckDB database via the manifest. Data files are in `data/raw/`. If the relative path doesn't work, you are in a git worktree — use absolute paths derived from the manifest instead:

```python
import duckdb
import json
from pathlib import Path

manifest = json.loads(Path(".team-agent/manifest.json").read_text())
project_id = manifest["project_id"]
data_dir = f"/data/projects/{project_id}/repo/data/raw"
db_path = f"/data/projects/{project_id}/databases/data.duckdb"
conn = duckdb.connect(db_path)
```

## Column naming

Every ingestion script must rename columns to SQL-friendly names as part of the SELECT. This is not optional — source files commonly have spaces, special characters, and mixed case in column headers. Always rename inline:

```python
conn.execute("""
    CREATE OR REPLACE TABLE l10wrk_customers AS
    SELECT
        "Customer ID" AS customer_id,
        "First Name" AS first_name,
        "Email Address" AS email,
        "DOB" AS date_of_birth
    FROM read_csv_auto('data/raw/customers.csv')
""")
```

Column names must be lowercase, alphanumeric and underscores only.

## Reading different file types

DuckDB can natively read multiple file formats:

### CSV / TSV

```python
conn.execute("""
    CREATE OR REPLACE TABLE l10wrk_sales AS
    SELECT * FROM read_csv_auto('data/raw/sales.csv')
""")
```

`read_csv_auto` detects delimiters, headers, and types automatically. For TSV or other delimiters, it handles them without extra configuration.

### Parquet

```python
conn.execute("""
    CREATE OR REPLACE TABLE l10wrk_events AS
    SELECT * FROM read_parquet('data/raw/events.parquet')
""")
```

Parquet files typically have correct types already — minimal transformation needed.

### JSON

```python
conn.execute("""
    CREATE OR REPLACE TABLE l10wrk_logs AS
    SELECT * FROM read_json_auto('data/raw/logs.json')
""")
```

Works with both JSON arrays and newline-delimited JSON (NDJSON).

### Excel

```python
conn.execute("INSTALL spatial; LOAD spatial;")
conn.execute("""
    CREATE OR REPLACE TABLE l10wrk_report AS
    SELECT * FROM st_read('data/raw/report.xlsx', layer = 'Sheet1')
""")
```

If DuckDB's Excel reading is problematic, fall back to pandas:

```python
import pandas as pd

df = pd.read_excel("data/raw/report.xlsx", sheet_name="Sheet1")
conn.execute("CREATE OR REPLACE TABLE l10wrk_report AS SELECT * FROM df")
```

## Strategy: start optimistic

Try DuckDB-native ingestion first with column renaming and type overrides. If the file is clean, this is the entire script:

```python
conn.execute("""
    CREATE OR REPLACE TABLE l10wrk_sales AS
    SELECT
        "Customer ID" AS customer_id,
        CAST("Order Date" AS DATE) AS order_date,
        "Region" AS region,
        CAST("Revenue" AS DOUBLE) AS revenue
    FROM read_csv_auto('data/raw/sales.csv')
""")
```

## Handling faulty rows

When the optimistic approach fails (type errors, malformed rows), use `store_rejects` to let good rows through while capturing the bad ones:

```python
conn.execute("""
    CREATE OR REPLACE TABLE l10wrk_sales AS
    SELECT
        CAST(customer_id AS INTEGER) AS customer_id,
        CAST(order_date AS DATE) AS order_date,
        region,
        revenue
    FROM read_csv_auto('data/raw/sales.csv', store_rejects = true)
""")

# Inspect what failed
rejects = conn.execute("""
    SELECT line, column_name, column_type, csv_line, error_message
    FROM reject_errors
""").fetchall()

for r in rejects:
    print(f"Line {r[0]}, column '{r[1]}' ({r[2]}): {r[4]}")
    print(f"  Raw: {r[3]}")
```

This gives the exact line number, column, original CSV content, and error message for each rejected row.

## Resolving rejected rows

After inspecting the rejects, fix and insert them. Choose the approach based on complexity:

### Simple fix in DuckDB (e.g. alternative date format)

```python
# Rejected rows had dates like 'Mar 15, 21' instead of '2021-03-15'
conn.execute("""
    INSERT INTO l10wrk_sales
    SELECT
        CAST(customer_id AS INTEGER),
        strptime(order_date, '%b %d, %y')::DATE,
        region,
        revenue
    FROM read_csv('data/raw/sales.csv', auto_detect = false, columns = {
        'customer_id': 'VARCHAR',
        'order_date': 'VARCHAR',
        'region': 'VARCHAR',
        'revenue': 'DOUBLE'
    })
    WHERE rowid IN (SELECT line FROM reject_errors)
""")
```

### Complex fix with pandas (e.g. regex parsing, multi-format cleanup)

When the cleaning logic is genuinely easier in Python:

```python
import pandas as pd

# Read rejected rows into a DataFrame for flexible manipulation
df_rejects = conn.execute("""
    SELECT csv_line FROM reject_errors
""").fetchdf()

# Parse and fix in Python, then insert back
# ... custom logic ...

conn.execute("INSERT INTO l10wrk_sales SELECT * FROM df_fixed")
```

## Multi-file datasets

When a dataset is split across multiple files (e.g. `sales_2021.csv`, `sales_2022.csv`), create one `l10wrk_` table — not one per file.

### Same schema — use glob

```python
conn.execute("""
    CREATE OR REPLACE TABLE l10wrk_sales AS
    SELECT * FROM read_csv_auto('data/raw/sales_*.csv')
""")
```

### Different column order or varying columns — use union_by_name

```python
conn.execute("""
    CREATE OR REPLACE TABLE l10wrk_sales AS
    SELECT * FROM read_csv_auto('data/raw/sales_*.csv', union_by_name = true)
""")
```

Missing columns in some files are filled with NULL.

### Incompatible formats — multiple inserts in one script

When files can't be globbed (different delimiters, headers, etc.), do multiple inserts into the same table:

```python
conn.execute("""
    CREATE OR REPLACE TABLE l10wrk_sales AS
    SELECT
        CAST(id AS INTEGER) AS customer_id,
        CAST(date AS DATE) AS order_date,
        region,
        CAST(amount AS DOUBLE) AS revenue
    FROM read_csv_auto('data/raw/sales_2021.csv')
""")

conn.execute("""
    INSERT INTO l10wrk_sales
    SELECT
        CAST(cust_id AS INTEGER) AS customer_id,
        CAST(order_dt AS DATE) AS order_date,
        sales_region AS region,
        CAST(rev AS DOUBLE) AS revenue
    FROM read_csv_auto('data/raw/sales_2022.csv')
""")
```

## Type conversion patterns

### Dates wrongly read as integers

```sql
strptime(CAST(order_date AS VARCHAR), '%Y%m%d')::DATE
```

### Dates as non-standard strings

```sql
strptime(order_date, '%d%b%y')::DATE    -- e.g. '04sep26'
strptime(order_date, '%d-%b-%Y')::DATE  -- e.g. '15-Mar-2023'
```

### Boolean from string values

```sql
CASE WHEN is_active IN ('Y', 'yes', 'true', '1') THEN TRUE ELSE FALSE END AS is_active
```

## Script ending

Every script should print a summary:

```python
row_count = conn.execute("SELECT COUNT(*) FROM l10wrk_sales").fetchone()[0]
col_count = len(conn.execute("DESCRIBE l10wrk_sales").fetchall())
print(f"Created l10wrk_sales: {row_count:,} rows, {col_count} columns")
```
