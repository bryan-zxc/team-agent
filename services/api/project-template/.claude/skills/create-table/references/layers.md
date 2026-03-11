# Data Layer Naming Convention

Tables are organised into layers numbered 10, 20, 30 — loosely corresponding to the bronze/silver/gold pattern. Gaps in the numbering allow custom intermediate layers (e.g. l15, l25) when needed.

## Layers

### l10wrk — Working

Tables created by ingesting source files (CSV, Excel, Parquet) into DuckDB with properly typed columns.

- **Naming**: `l10wrk_<descriptive_name>` (e.g. `l10wrk_customers`, `l10wrk_sales`)
- **Script**: `analysis/l10wrk_<name>.py` — Python script using pandas for type conversion
- **Source**: files in `data/raw/`

### l20drv — Derived

Tables created by transforming, joining, or aggregating working tables or other derived tables. Business logic lives here.

- **Naming**: `l20drv_<descriptive_name>` (e.g. `l20drv_sales_by_region`, `l20drv_customer_lifetime`)
- **Script**: `analysis/l20drv_<name>.sql` — SQL CREATE TABLE AS SELECT

### l30exp — Export

Tables shaped for consumption by reporting, dashboards, or external systems. Minimal transformation — primarily filtering, renaming, and formatting from derived tables.

- **Naming**: `l30exp_<descriptive_name>` (e.g. `l30exp_monthly_revenue`)
- **Script**: `analysis/l30exp_<name>.sql` — SQL CREATE TABLE AS SELECT

## Rules

- One script per table, no exceptions. The script is named identically to the table it produces (e.g. table `l10wrk_customers` → script `analysis/l10wrk_customers.py`)
- Always lowercase with underscores
- Prefix must match the layer exactly (e.g. `l10wrk_`, not `l10_wrk_`)
- Name should describe the content, not the source file (e.g. `l10wrk_customers` not `l10wrk_customers_csv`)
