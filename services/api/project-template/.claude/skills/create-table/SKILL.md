---
name: create-table
description: Create a new table in the project's DuckDB database. Use this skill whenever the user wants to load data from a file, create a derived table from existing tables, or build an export table for reporting. Triggers on "create table", "load data", "ingest file", "import csv", "new table", "derived table", "export table", or any request to get data into DuckDB.
---

# Create Table

Route to the appropriate sub-skill based on what the user wants to do.

## Determining the table type

Ask the user if unclear, but most requests fall into obvious categories:

- **Working table** — the user has a file (CSV, Excel, Parquet) they want to load into DuckDB. Invoke `/create-work-table`.
- **Analysis table** — the user wants to create a new table by querying or transforming existing tables. Invoke `/create-analysis-table`.

## Important: data only

Only actual data should be uploaded and turned into tables. Metadata such as data dictionaries, field descriptions, and informational content — even if it arrives in tabular form (e.g. a CSV of column definitions) — should not be ingested as a table. Instead, incorporate that information into the relevant table's markdown documentation in `docs/tables/` as key notes or column descriptions.

## Layer overview

Read `references/layers.md` for the full naming convention. In short:

| Layer | Prefix | What it holds |
|-------|--------|---------------|
| Working | `l10wrk_` | Typed, cleaned data from source files |
| Derived | `l20drv_` | Transformations from wrk or other drv tables |
| Export | `l30exp_` | Final tables consumed by reporting |

Layer numbers use gaps (10, 20, 30) so users can introduce custom intermediate layers (e.g. l15, l25) when needed.
