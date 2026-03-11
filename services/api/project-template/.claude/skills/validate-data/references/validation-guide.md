# Validation Guide

Common data check patterns with SQL examples. Adapt these to the specific tables and columns in the project.

## Connecting to DuckDB

```python
import json
import duckdb
from pathlib import Path

manifest = json.loads(Path(".team-agent/manifest.json").read_text())
project_id = manifest["project_id"]
db_path = f"/data/projects/{project_id}/databases/data.duckdb"
conn = duckdb.connect(db_path)
```

## Primary key uniqueness

Verify that a column or set of columns uniquely identifies each row.

```sql
-- Single column PK
SELECT customer_id, COUNT(*) AS cnt
FROM l10wrk_customers
GROUP BY customer_id
HAVING COUNT(*) > 1;

-- Composite PK
SELECT region, quarter, COUNT(*) AS cnt
FROM l20drv_sales_by_region
GROUP BY region, quarter
HAVING COUNT(*) > 1;
```

Zero rows = the key is valid. Any rows = duplicates exist.

## Join completeness

Check what exists in one table but not the other before joining. Also verify match rates and categorical consistency.

```sql
-- Orders referencing customers that don't exist
SELECT o.order_id, o.customer_id
FROM l10wrk_orders o
LEFT JOIN l10wrk_customers c ON o.customer_id = c.customer_id
WHERE c.customer_id IS NULL;
```

Match rate summary:

```sql
SELECT
    COUNT(*) AS total_orders,
    COUNT(c.customer_id) AS matched,
    COUNT(*) - COUNT(c.customer_id) AS unmatched,
    ROUND(100.0 * COUNT(c.customer_id) / COUNT(*), 1) AS match_pct
FROM l10wrk_orders o
LEFT JOIN l10wrk_customers c ON o.customer_id = c.customer_id;
```

Categorical consistency — when two tables share a column used for joining, check for value mismatches:

```sql
-- Categories in orders but not in the reference table
SELECT DISTINCT o.category
FROM l10wrk_orders o
LEFT JOIN l10wrk_categories c ON o.category = c.category
WHERE c.category IS NULL;
```

## Join key is PK on one side

Before joining, verify the join key is a primary key on at least one table. If it's not, the join will produce row multiplication.

```sql
-- Check if customer_id is unique in customers (should return 0 rows)
SELECT customer_id, COUNT(*) AS cnt
FROM l10wrk_customers
GROUP BY customer_id
HAVING COUNT(*) > 1;
```

If the join key is NOT unique on either side, you have a many-to-many join — this almost always indicates a problem. Investigate before proceeding.

## Division by zero

Check for zeros in columns you plan to divide by.

```sql
SELECT category, total_revenue, order_count
FROM l20drv_category_summary
WHERE order_count = 0;
```

## Null rate in critical columns

Check null rates in columns needed for the analysis.

```sql
SELECT
    COUNT(*) AS total_rows,
    COUNT(revenue) AS non_null,
    COUNT(*) - COUNT(revenue) AS null_count,
    ROUND(100.0 * (COUNT(*) - COUNT(revenue)) / COUNT(*), 1) AS null_pct
FROM l10wrk_sales;
```

## Unexpected negatives

Check for negative values in columns expected to be positive.

```sql
SELECT *
FROM l10wrk_sales
WHERE revenue < 0;
```

A small number of negatives may be refunds (expected). A large number may indicate a data issue.

## Date range coverage

Verify the data covers the expected analysis period.

```sql
SELECT
    MIN(order_date) AS earliest,
    MAX(order_date) AS latest,
    COUNT(DISTINCT DATE_TRUNC('month', order_date)) AS months_covered
FROM l10wrk_sales
WHERE order_date IS NOT NULL;
```

## Future dates

Check for dates in the future that may be test data or errors.

```sql
SELECT *
FROM l10wrk_sales
WHERE order_date > CURRENT_DATE;
```

## Duplicate rows (exact)

Check for completely identical rows.

```sql
SELECT *, COUNT(*) AS cnt
FROM l10wrk_sales
GROUP BY ALL
HAVING COUNT(*) > 1;
```
