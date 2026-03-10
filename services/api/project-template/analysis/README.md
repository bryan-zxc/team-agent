# Analysis

Python and SQL scripts for data analysis.

Scripts are executed via `run.py` using a `pipeline.yml` configuration that defines execution order, inputs, outputs, and validation checks.

## Script naming conventions

Each table has one creation script named after the table it produces:

| Layer | Prefix | Script | Purpose |
|-------|--------|--------|---------|
| Working | `l10wrk_` | `l10wrk_<name>.py` | Ingest file into DuckDB with typed columns |
| Derived | `l20drv_` | `l20drv_<name>.sql` | Transform from wrk/drv tables |
| Export | `l30exp_` | `l30exp_<name>.sql` | Final tables for reporting consumption |

Layer numbers use gaps (10, 20, 30) to allow custom intermediate layers (e.g. l15, l25).
