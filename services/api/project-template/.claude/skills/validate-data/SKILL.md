---
name: validate-data
description: Orchestrate data validation — ingest raw data, extract analysis requirements, plan delivery, and confirm data fitness. Use when the user wants to validate data, check data quality, start a new analysis engagement, or run data checks. Triggers on "validate data", "data validation", "check data quality", "start analysis", "data fitness", or any request to systematically review data before analysis.
---

# Validate Data

End-to-end data validation workflow: ingest raw data, agree analysis requirements with the client, plan the delivery, then systematically confirm data fitness. This skill can be invoked multiple times — it always checks current state first.

## Data and database paths

```python
import json
from pathlib import Path

manifest = json.loads(Path(".team-agent/manifest.json").read_text())
project_id = manifest["project_id"]
data_dir = f"/data/projects/{project_id}/repo/data/raw"
db_path = f"/data/projects/{project_id}/databases/data.duckdb"
```

## Workflow

### Phase 0: State check

On every invocation, assess current state before leading the user. Check:

1. What files are in `data/raw/`?
2. What tables are documented in `docs/tables/tables.md`?
3. What's in `data/validation/data-check-register.md`? (any checks recorded?)
4. What's in `data/validation/report_data.json`? (any issues raised?)
5. What's in `analysis/README.md`? (any agreed deliverables?)
6. Does `analysis/pipeline.yml` exist? (any pipeline steps defined?)

Based on the state, determine which phase to resume from:
- No tables documented and raw files exist → start at Phase 1
- Tables exist but no analysis plan → start at Phase 2
- Analysis plan exists but no delivery plan → start at Phase 3
- Delivery plan exists but checks are incomplete → start at Phase 4
- Everything done → brief the user on current state, ask what's next

Present the state assessment to the user before proceeding.

### Phase 1: Ingest raw data

Walk through `data/raw/` and convert each data file to a working table using `/create-work-table`.

**What to ingest:**
- CSV, TSV, Excel, Parquet, JSON files containing actual data rows

**What NOT to ingest:**
- Data dictionaries, field descriptions, column definitions, mapping reference documents — even if they arrive in tabular format (CSV, Excel). These are metadata, not data. Bake their content into the relevant table's markdown documentation in `docs/tables/` as key notes or column descriptions.
- README files, instructions, cover pages

For each file, confirm with the user before ingesting. Follow the `/create-work-table` workflow fully (sample, type review, ingest, document).

**During ingestion:** if parsing errors are encountered — rows rejected due to type mismatches, non-standard date formats that fail to parse, malformed values that prevent clean ingestion — use `/append-dv` to log these as data validation issues. These are rows that could not be ingested cleanly and need client input on how to handle them. Do not raise issues for data quality concerns like duplicates or unexpected values at this stage — those are investigated in Phase 4.

Continue until all data files are ingested.

### Phase 2: Extract analysis requirements

Read `docs/pre-engagement/` for the statement of work, engagement letter, or project scope.

The pre-engagement documents may be vague in their description of the analysis. Your job is to work with the human to agree a set of **tangible, deliverable analysis outcomes**.

Use the table documentation created in Phase 1 to ground the conversation:
- "Here's what data we have: [summary of tables and key columns]"
- "Based on the scope, I believe we need to deliver: [proposed deliverables]"

Push for specificity. Vague requirements like "analyse sales performance" must be broken down into concrete outputs: "Monthly revenue by region table", "Top 10 products by revenue dashboard", "Customer churn analysis with cohort breakdown".

**We must deliver to the scope of analysis — that is non-optional.** If we identify that we cannot deliver a required outcome due to missing data, it means we need to ask the client for more data. It does not mean we exclude the deliverable from the analysis.

On agreement, update `analysis/README.md` with the confirmed analysis plan:
- List of agreed deliverables
- Approach for each deliverable
- Data dependencies (which tables are needed)
- Any data gaps that require additional data from the client

### Phase 3: Plan delivery

Enter plan mode to design the full analysis delivery.

The plan should specify:
- What derived tables (`l20drv_`) to create, with their SQL logic
- What joins are needed between which tables
- What calculations and aggregations to perform
- What export tables (`l30exp_`) to produce for final reporting
- What pipeline steps and their execution order

This plan directly informs Phase 4 — every table, join, and calculation in the plan becomes something we need to validate data fitness for.

Exit plan mode on user approval before proceeding.

### Phase 4: Data fitness investigation

Systematically confirm the data supports every step in the delivery plan. For each analytical operation planned, run the relevant checks using `/record-data-check`.

Read `references/validation-guide.md` for common check patterns with SQL examples.

#### Table and column coverage

- Do we have every table needed for the planned analysis?
- Do we have every column needed? Are any critical columns missing?
- If data gaps are identified, raise with the client — we need the data, not a reduced scope.

#### Primary key validation

Primary key of every table we plan to use must be understood — unless we have no intention of using that table at all.

- `l10wrk_` working tables: PK is not mandatory (transaction data may not have a natural key), but if a key is expected, verify it
- `l20drv_` derived tables and onward: PK is compulsory — this is enforced by `/create-analysis-table`

For each table:
- Identify the expected primary key columns
- Run a uniqueness check via `/record-data-check`
- Record the confirmed PK in the table's markdown documentation and in `pipeline.yml` as a check

#### Join condition validation

For every planned join between two tables:

- **Completeness:** what is in one table and not the other? What proportion actually matches? Is the mismatch expected?
- **Key integrity:** the complete set of join conditions must be a primary key on at least one of the two tables being joined. If this is not satisfied, the join will produce unexpected row multiplication. Verify this before proceeding.
- **Categorical consistency:** when two tables share a categorical column used for joining, verify the values are consistent — check for mismatches, misspellings, mixed case, or values in one table that don't exist in the other.
- Run each join check via `/record-data-check`

#### Arithmetic safety

For calculations in the planned analysis:

- **Division:** if dividing by a column, check for zero values. How many? Are they expected?
- **Numerical fields:** are there unexpected negative numbers? Unexpected nulls? Values that are orders of magnitude outside the expected range?
- Run each check via `/record-data-check`

#### Domain-specific checks

Based on the specific analysis being planned, additional checks may be needed:
- Date range coverage (does the data span the full analysis period?)
- Currency/unit consistency (are amounts in the same currency?)
- Temporal ordering (are timestamps in logical order?)

These are examples, not an exhaustive list. The point is: every assumption the analysis depends on must be verified, and every verification must be recorded.

#### Completion

Once all checks are complete and any data validation issues are raised, brief the user:
- Summary of checks run (total, pass, fail)
- Issues raised in the data validation report
- Any blockers that prevent proceeding with analysis
- Recommended next steps
